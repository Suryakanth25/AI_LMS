"""
RAG Retriever v2 — Hybrid vector + BM25 retrieval with cross-encoder reranking.
Main entry point: retrieve_context_for_generation()
"""
import time
import numpy as np
from rank_bm25 import BM25Okapi

from services.rag import _get_collection, embedding_fn, _mmr_rerank
from services.rag_query_builder import build_query_variants, QueryVariant


# ─── Cross-Encoder (lazy loaded) ───

_cross_encoder = None

def _get_cross_encoder():
    """Lazy-load the cross-encoder model to avoid startup overhead."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            print("[RAG-V2] Cross-encoder loaded: ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            print(f"[RAG-V2] Cross-encoder unavailable: {e}")
            _cross_encoder = False  # Sentinel: tried and failed
    return _cross_encoder if _cross_encoder is not False else None


# ─── BM25 Scoring ───

def _compute_bm25_scores(query_text: str, documents: list[str]) -> dict[int, float]:
    """Compute BM25 scores for each document against the query."""
    if not documents:
        return {}
    
    # Tokenize documents
    tokenized_docs = [doc.lower().split() for doc in documents]
    bm25 = BM25Okapi(tokenized_docs)
    
    # Score against query
    query_tokens = query_text.lower().split()
    scores = bm25.get_scores(query_tokens)
    
    # Normalize scores to [0, 1]
    max_score = float(max(scores)) if len(scores) > 0 and max(scores) > 0 else 1.0
    return {i: float(scores[i]) / max_score for i in range(len(documents))}


# ─── Hybrid Score Fusion ───

def _fuse_scores(
    vector_scores: dict[str, float],
    bm25_scores: dict[str, float],
    alpha: float = 0.6,
) -> dict[str, float]:
    """
    Fuse vector similarity and BM25 scores.
    score = alpha * vector + (1 - alpha) * bm25
    """
    all_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
    fused = {}
    for doc_id in all_ids:
        v_score = vector_scores.get(doc_id, 0.0)
        b_score = bm25_scores.get(doc_id, 0.0)
        fused[doc_id] = alpha * v_score + (1 - alpha) * b_score
    return fused


# ─── Vector Retrieval ───

def _vector_retrieve(
    collection,
    query_text: str,
    fetch_k: int,
    where_clause: dict = None,
) -> tuple[list[str], list[str], list[list[float]], list[float]]:
    """
    Perform ChromaDB vector retrieval for a single query.
    Returns: (documents, ids, embeddings, distances)
    """
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=fetch_k,
            where=where_clause,
            include=["documents", "embeddings", "distances", "metadatas"],
        )
        
        docs_result = results.get("documents")
        ids_result = results.get("ids")
        embs_result = results.get("embeddings")
        dist_result = results.get("distances")
        
        docs = list(docs_result[0]) if docs_result is not None and len(docs_result) > 0 else []
        ids = list(ids_result[0]) if ids_result is not None and len(ids_result) > 0 else []
        embs = list(embs_result[0]) if embs_result is not None and len(embs_result) > 0 else []
        dists = list(dist_result[0]) if dist_result is not None and len(dist_result) > 0 else []
        
        return docs, ids, embs, dists
    except Exception as e:
        print(f"[RAG-V2] Vector retrieval error: {e}")
        return [], [], [], []


def _distances_to_scores(distances: list[float]) -> list[float]:
    """Convert ChromaDB distances (lower=better) to similarity scores (higher=better)."""
    if not distances:
        return []
    # ChromaDB uses L2 distance by default — convert to similarity
    # score = 1 / (1 + distance)
    return [1.0 / (1.0 + d) for d in distances]


# ─── Main Entry Point ───

def retrieve_context_for_generation(
    subject_id: int,
    unit_id: int = None,
    topic_id: int = None,
    topic_name: str = "",
    unit_name: str = "",
    lo_text: str = "",
    co_text: str = "",
    bloom_level: str = "",
    difficulty: str = "Medium",
    question_type: str = "MCQ",
    n_results: int = 10,
    fetch_k: int = 100,
    alpha: float = 0.6,
    use_cross_encoder: bool = True,
    cross_encoder_top_k: int = 50,
    chunk_usage_counts: dict = None,
    chunk_usage_penalty: float = 0.1,
) -> dict:
    """
    Main retrieval function for question generation.
    
    Pipeline:
    1. Build query variants from structured inputs
    2. Vector retrieve for each variant (scoped → fallback)
    3. Merge & dedup candidates
    4. BM25 scoring + hybrid fusion
    5. Optional cross-encoder reranking
    6. MMR diversity selection
    
    Returns: {
        "chunks": list[str],
        "chunk_ids": list[str],
        "debug_info": { ... }
    }
    """
    pipeline_start = time.time()
    debug_info = {
        "query_variants": [],
        "total_candidates": 0,
        "vector_scores": {},
        "bm25_scores": {},
        "reranker_scores": {},
        "final_ranking": [],
        "pipeline_time_seconds": 0,
    }
    
    # ─── Step 1: Build query variants ───
    variants = build_query_variants(
        topic_name=topic_name,
        lo_text=lo_text,
        co_text=co_text,
        bloom_level=bloom_level,
        difficulty=difficulty,
        question_type=question_type,
    )
    debug_info["query_variants"] = [
        {"text": v.text, "strategy": v.strategy, "weight": v.weight}
        for v in variants
    ]
    print(f"[RAG-V2] Query variants ({len(variants)}): {[v.strategy for v in variants]}")
    
    # ─── Step 2: Vector retrieval for each variant ───
    collection_name = f"subject_{subject_id}"
    try:
        collection = _get_collection(collection_name)
        if collection.count() == 0:
            print("[RAG-V2] Collection empty — no chunks to retrieve")
            return {"chunks": [], "chunk_ids": [], "debug_info": debug_info}
    except Exception as e:
        print(f"[RAG-V2] Collection error: {e}")
        return {"chunks": [], "chunk_ids": [], "debug_info": debug_info}
    
    # Build scoped where clause
    where_clause = None
    if topic_id:
        where_clause = {"topic_id": str(topic_id)}
    elif unit_id:
        where_clause = {"unit_id": str(unit_id)}
    
    # Collect candidates across all query variants
    all_candidates = {}  # chunk_id -> {doc, embedding, best_vector_score}
    
    for variant in variants:
        # Try scoped retrieval first
        docs, ids, embs, dists = _vector_retrieve(
            collection, variant.text, fetch_k, where_clause
        )
        
        # Fallback to subject-wide if scoped returns nothing
        if len(docs) == 0 and where_clause is not None:
            docs, ids, embs, dists = _vector_retrieve(
                collection, variant.text, fetch_k, None
            )
        
        scores = _distances_to_scores(dists)
        
        for i, chunk_id in enumerate(ids):
            weighted_score = scores[i] * variant.weight if i < len(scores) else 0.0
            
            if chunk_id not in all_candidates:
                all_candidates[chunk_id] = {
                    "doc": docs[i],
                    "embedding": embs[i] if i < len(embs) else None,
                    "best_vector_score": weighted_score,
                    "variant_hits": 1,
                }
            else:
                # Keep the best score + count how many variants found this chunk
                existing = all_candidates[chunk_id]
                existing["best_vector_score"] = max(existing["best_vector_score"], weighted_score)
                existing["variant_hits"] += 1
    
    total_candidates = len(all_candidates)
    debug_info["total_candidates"] = total_candidates
    print(f"[RAG-V2] Vector candidates: {total_candidates} (from {len(variants)} queries)")
    
    if total_candidates == 0:
        return {"chunks": [], "chunk_ids": [], "debug_info": debug_info}
    
    # ─── Step 3: Prepare candidate lists ───
    candidate_ids = list(all_candidates.keys())
    candidate_docs = [all_candidates[cid]["doc"] for cid in candidate_ids]
    candidate_embs = [all_candidates[cid]["embedding"] for cid in candidate_ids]
    vector_scores_map = {cid: all_candidates[cid]["best_vector_score"] for cid in candidate_ids}
    
    # Bonus for chunks found by multiple query variants (reinforcement)
    for cid in candidate_ids:
        hits = all_candidates[cid]["variant_hits"]
        if hits > 1:
            vector_scores_map[cid] *= (1 + 0.05 * (hits - 1))  # 5% bonus per extra hit
    
    debug_info["vector_scores"] = {cid: round(s, 4) for cid, s in list(vector_scores_map.items())[:10]}
    
    # ─── Step 4: BM25 scoring ───
    # Build a combined query from all variants for BM25
    combined_query = " ".join([v.text for v in variants[:4]])  # Use top 4 variants
    bm25_idx_scores = _compute_bm25_scores(combined_query, candidate_docs)
    bm25_scores_map = {candidate_ids[i]: bm25_idx_scores.get(i, 0.0) for i in range(len(candidate_ids))}
    
    debug_info["bm25_scores"] = {cid: round(s, 4) for cid, s in list(bm25_scores_map.items())[:10]}
    
    # ─── Step 5: Hybrid fusion ───
    fused_scores = _fuse_scores(vector_scores_map, bm25_scores_map, alpha=alpha)
    
    # Apply chunk usage penalty (if provided by novelty module)
    if chunk_usage_counts:
        for cid in fused_scores:
            usage = chunk_usage_counts.get(cid, 0)
            if usage > 0:
                fused_scores[cid] *= max(0.3, 1.0 - chunk_usage_penalty * usage)
    
    # Sort by fused score
    ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    
    # ─── Step 6: Cross-encoder reranking (optional) ───
    reranker_used = False
    if use_cross_encoder and total_candidates >= 5:
        cross_encoder = _get_cross_encoder()
        if cross_encoder is not None:
            try:
                top_k_for_rerank = min(cross_encoder_top_k, len(ranked))
                rerank_ids = [r[0] for r in ranked[:top_k_for_rerank]]
                rerank_docs = [all_candidates[cid]["doc"] for cid in rerank_ids]
                
                # Cross-encoder scores: pairs of (query, doc)
                # Use the primary query (topic + LO) for reranking
                primary_query = variants[0].text
                pairs = [(primary_query, doc) for doc in rerank_docs]
                
                ce_start = time.time()
                ce_scores = cross_encoder.predict(pairs)
                ce_time = time.time() - ce_start
                
                # Normalize CE scores to [0, 1]
                ce_min = float(min(ce_scores))
                ce_max = float(max(ce_scores))
                ce_range = ce_max - ce_min if ce_max > ce_min else 1.0
                
                # Replace fused scores with CE scores for reranked candidates
                for i, cid in enumerate(rerank_ids):
                    ce_normalized = (float(ce_scores[i]) - ce_min) / ce_range
                    fused_scores[cid] = ce_normalized
                
                # Re-sort
                ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
                reranker_used = True
                
                debug_info["reranker_scores"] = {
                    rerank_ids[i]: round(float(ce_scores[i]), 4)
                    for i in range(min(10, len(rerank_ids)))
                }
                print(f"[RAG-V2] Cross-encoder reranked {top_k_for_rerank} candidates in {ce_time:.2f}s")
                
            except Exception as e:
                print(f"[RAG-V2] Cross-encoder reranking failed: {e}")
    
    # ─── Step 7: MMR diversity selection ───
    # Take top candidates and apply MMR for diverse final selection
    top_n_for_mmr = min(max(n_results * 3, 15), len(ranked))
    mmr_ids = [r[0] for r in ranked[:top_n_for_mmr]]
    mmr_docs = [all_candidates[cid]["doc"] for cid in mmr_ids]
    mmr_embs = [all_candidates[cid]["embedding"] for cid in mmr_ids]
    
    # Filter out None embeddings
    valid_indices = [i for i, e in enumerate(mmr_embs) if e is not None]
    
    if valid_indices and len(valid_indices) >= n_results:
        valid_docs = [mmr_docs[i] for i in valid_indices]
        valid_embs = [mmr_embs[i] for i in valid_indices]
        valid_ids = [mmr_ids[i] for i in valid_indices]
        
        query_embedding = embedding_fn([variants[0].text])[0]
        final_docs = _mmr_rerank(query_embedding, valid_embs, valid_docs, k=n_results, lambda_mult=0.7)
        
        # Map back to IDs
        doc_to_id = {doc: cid for doc, cid in zip(valid_docs, valid_ids)}
        final_ids = [doc_to_id.get(doc, "") for doc in final_docs]
    else:
        # Fallback: just take top ranked
        final_docs = [all_candidates[r[0]]["doc"] for r in ranked[:n_results]]
        final_ids = [r[0] for r in ranked[:n_results]]
    
    pipeline_time = time.time() - pipeline_start
    debug_info["pipeline_time_seconds"] = round(pipeline_time, 3)
    debug_info["reranker_used"] = reranker_used
    debug_info["final_ranking"] = [
        {"chunk_id": cid, "score": round(fused_scores.get(cid, 0), 4)}
        for cid in final_ids
    ]
    
    print(f"[RAG-V2] Final chunks: {len(final_docs)} (diverse) | Pipeline: {pipeline_time:.2f}s")
    
    return {
        "chunks": final_docs,
        "chunk_ids": final_ids,
        "debug_info": debug_info,
    }
