"""
Novelty & Grounding — question dedup, chunk usage tracking, and grounding validation.

- check_novelty(): detect duplicate questions by embedding similarity
- validate_grounding(): verify a generated question is supported by source material
- get_chunk_usage_counts(): track overused chunks for retriever penalty
"""
import numpy as np
from collections import defaultdict
from typing import Optional

from services.rag import embedding_fn, _get_collection


# ─── In-Memory Caches ───
# These are populated on first use and updated as questions are approved/rejected.

_question_embeddings_cache: dict[str, list[dict]] = {}  # key: "subject_topic" -> [{embedding, question_id, text}]
_chunk_usage_cache: dict[str, dict[str, int]] = {}  # key: "subject_topic" -> {chunk_id: usage_count}


def _cache_key(subject_id: int, topic_id: int = None) -> str:
    """Generate a cache key for a subject/topic pair."""
    return f"s{subject_id}_t{topic_id or 'all'}"


def _cosine_similarity(vec_a, vec_b) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ─── Question Novelty / Dedup ───

def load_existing_questions(db, subject_id: int, topic_id: int = None):
    """
    Load embeddings for existing pending+approved questions into the cache.
    Called lazily on first check_novelty() call for a given subject/topic.
    """
    from models import GeneratedQuestion
    
    key = _cache_key(subject_id, topic_id)
    if key in _question_embeddings_cache:
        return  # Already loaded
    
    query = db.query(GeneratedQuestion).filter(
        GeneratedQuestion.status.in_(["pending", "approved"]),
    )
    
    if topic_id:
        query = query.filter(GeneratedQuestion.topic_id == topic_id)
    
    questions = query.all()
    
    # Embed all question texts
    entries = []
    for q in questions:
        if q.text and len(q.text.strip()) > 10:
            try:
                emb = embedding_fn([q.text])[0]
                entries.append({
                    "embedding": emb,
                    "question_id": q.id,
                    "text": q.text[:200],  # Truncated for debug
                })
            except Exception:
                pass
    
    _question_embeddings_cache[key] = entries
    print(f"[Novelty] Loaded {len(entries)} existing question embeddings for {key}")


def check_novelty(
    db,
    subject_id: int,
    question_text: str,
    topic_id: int = None,
    similarity_threshold: float = 0.85,
) -> dict:
    """
    Check if a new question is too similar to existing questions.
    
    Returns: {
        "is_novel": bool,
        "max_similarity": float,
        "similar_question_id": int or None,
        "similar_question_text": str or None,
    }
    """
    # Ensure cache is loaded
    load_existing_questions(db, subject_id, topic_id)
    
    key = _cache_key(subject_id, topic_id)
    existing = _question_embeddings_cache.get(key, [])
    
    if not existing:
        return {
            "is_novel": True,
            "max_similarity": 0.0,
            "similar_question_id": None,
            "similar_question_text": None,
        }
    
    # Embed the new question
    try:
        new_emb = embedding_fn([question_text])[0]
    except Exception:
        return {
            "is_novel": True,
            "max_similarity": 0.0,
            "similar_question_id": None,
            "similar_question_text": None,
        }
    
    # Find max similarity
    max_sim = 0.0
    best_match = None
    
    for entry in existing:
        sim = _cosine_similarity(new_emb, entry["embedding"])
        if sim > max_sim:
            max_sim = sim
            best_match = entry
    
    is_novel = max_sim < similarity_threshold
    
    return {
        "is_novel": is_novel,
        "max_similarity": round(max_sim, 4),
        "similar_question_id": best_match["question_id"] if best_match and not is_novel else None,
        "similar_question_text": best_match["text"] if best_match and not is_novel else None,
    }


def register_question(
    subject_id: int,
    topic_id: int,
    question_id: int,
    question_text: str,
    chunk_ids: list[str] = None,
):
    """
    Register a newly generated question into the novelty cache.
    Call this after a question is saved to the DB.
    """
    key = _cache_key(subject_id, topic_id)
    
    # Add to question embeddings cache
    if key not in _question_embeddings_cache:
        _question_embeddings_cache[key] = []
    
    try:
        emb = embedding_fn([question_text])[0]
        _question_embeddings_cache[key].append({
            "embedding": emb,
            "question_id": question_id,
            "text": question_text[:200],
        })
    except Exception:
        pass
    
    # Track chunk usage
    if chunk_ids:
        if key not in _chunk_usage_cache:
            _chunk_usage_cache[key] = {}
        for cid in chunk_ids:
            _chunk_usage_cache[key][cid] = _chunk_usage_cache[key].get(cid, 0) + 1


def get_chunk_usage_counts(subject_id: int, topic_id: int = None) -> dict[str, int]:
    """
    Get chunk usage counts for the retriever to penalize overused chunks.
    Returns: {chunk_id: usage_count}
    """
    key = _cache_key(subject_id, topic_id)
    return _chunk_usage_cache.get(key, {})


def clear_cache(subject_id: int = None, topic_id: int = None):
    """Clear novelty caches (e.g., after bulk operations)."""
    if subject_id is None:
        _question_embeddings_cache.clear()
        _chunk_usage_cache.clear()
    else:
        key = _cache_key(subject_id, topic_id)
        _question_embeddings_cache.pop(key, None)
        _chunk_usage_cache.pop(key, None)


# ─── Grounding Validator ───

def validate_grounding(
    subject_id: int,
    question_text: str,
    topic_id: int = None,
    similarity_threshold: float = 0.45,
    n_results: int = 5,
) -> dict:
    """
    Validate that a generated question is grounded in source material.
    
    Re-retrieves from ChromaDB using the question text as query,
    then checks if any retrieved chunk is sufficiently similar.
    
    Returns: {
        "is_grounded": bool,
        "grounding_score": float,
        "best_matching_chunk": str or None,
    }
    """
    collection_name = f"subject_{subject_id}"
    
    try:
        collection = _get_collection(collection_name)
        if collection.count() == 0:
            return {
                "is_grounded": False,
                "grounding_score": 0.0,
                "best_matching_chunk": None,
            }
        
        # Build where clause for scoped search
        where_clause = None
        if topic_id:
            where_clause = {"topic_id": str(topic_id)}
        
        # Retrieve using the question text as query
        results = collection.query(
            query_texts=[question_text],
            n_results=n_results,
            where=where_clause,
            include=["documents", "distances"],
        )
        
        docs_result = results.get("documents")
        dist_result = results.get("distances")
        
        docs = list(docs_result[0]) if docs_result is not None and len(docs_result) > 0 else []
        dists = list(dist_result[0]) if dist_result is not None and len(dist_result) > 0 else []
        
        if not docs:
            # Fallback: try without topic filter
            if where_clause is not None:
                results = collection.query(
                    query_texts=[question_text],
                    n_results=n_results,
                    include=["documents", "distances"],
                )
                docs_result = results.get("documents")
                dist_result = results.get("distances")
                docs = list(docs_result[0]) if docs_result is not None and len(docs_result) > 0 else []
                dists = list(dist_result[0]) if dist_result is not None and len(dist_result) > 0 else []
        
        if not docs:
            return {
                "is_grounded": False,
                "grounding_score": 0.0,
                "best_matching_chunk": None,
            }
        
        # Convert distances to similarity scores
        similarities = [1.0 / (1.0 + d) for d in dists]
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])
        
        return {
            "is_grounded": best_score >= similarity_threshold,
            "grounding_score": round(best_score, 4),
            "best_matching_chunk": docs[best_idx][:300] if best_idx < len(docs) else None,
        }
        
    except Exception as e:
        print(f"[Novelty] Grounding validation error: {e}")
        return {
            "is_grounded": True,  # Don't block on errors
            "grounding_score": 0.0,
            "best_matching_chunk": None,
        }
