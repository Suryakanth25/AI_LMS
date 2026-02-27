"""
RAG Retriever v2 — Hybrid vector + BM25 retrieval with cross-encoder reranking.
Main entry point: retrieve_context_for_generation()
"""
import time
import numpy as np
from rank_bm25 import BM25Okapi

from services.rag import _get_collection, embedding_fn, _mmr_rerank
from services.rag_query_builder import build_query_variants, QueryVariant
from services.redis_cache import RedisCache
from services.cached_embedding import cached_embedding_fn

_redis = RedisCache()

import requests
import re

def _is_noisy_chunk(text: str) -> bool:
    """
    Filter out chunks that are noise rather than content.
    These slip through when PDFs have headers, footers, TOCs, or index pages.
    """
    text = text.strip()
    
    # Too short to be meaningful
    if len(text) < 100:
        return True
    
    # Mostly numbers/punctuation (page numbers, index entries)
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    if alpha_ratio < 0.40:
        return True
    
    # Chapter/Index header patterns
    import re
    noise_patterns = [
        r'^\s*chapter\s+\d+\s*$',
        r'^\s*index\s*$',
        r'^\s*table\s+of\s+contents\s*$',
        r'^\s*references?\s*$',
        r'^\s*bibliography\s*$',
        r'^\s*appendix\s+[a-z]\s*$',
        r'^\s*\d{1,3}\s*$',  # Just a page number
    ]
    first_line = text.split('\n')[0].strip()
    for pattern in noise_patterns:
        if re.match(pattern, first_line, re.IGNORECASE):
            return True
    
    return False

def _cluster_by_proximity(
    candidate_ids: list[str],
    all_candidates: dict,
    max_page_gap: int = 5,
    min_cluster_size: int = 2,
) -> list[list[str]]:
    """
    Group candidate chunks into proximity clusters.
    """
    if not candidate_ids:
        return []

    # Sort chunks by (material_id, page_start, chunk_index)
    sorted_cids = sorted(
        candidate_ids,
        key=lambda cid: (
            all_candidates[cid].get("material_id", ""),
            all_candidates[cid].get("page_start", 0),
            all_candidates[cid].get("chunk_index", 0)
        )
    )

    clusters = []
    current_cluster = [sorted_cids[0]]

    for i in range(1, len(sorted_cids)):
        cid = sorted_cids[i]
        prev_cid = current_cluster[-1]

        mat_id = all_candidates[cid].get("material_id", "")
        prev_mat_id = all_candidates[prev_cid].get("material_id", "")
        
        page_start = all_candidates[cid].get("page_start", 0)
        prev_page_end = all_candidates[prev_cid].get("page_end", 0)
        
        c_idx = all_candidates[cid].get("chunk_index", 0)
        prev_c_idx = all_candidates[prev_cid].get("chunk_index", 0)

        is_same_material = (mat_id == prev_mat_id)
        is_page_close = abs(page_start - prev_page_end) <= max_page_gap
        is_index_close = abs(c_idx - prev_c_idx) <= 3

        if is_same_material and (is_page_close or is_index_close):
            current_cluster.append(cid)
        else:
            clusters.append(current_cluster)
            current_cluster = [cid]
            
    if current_cluster:
        clusters.append(current_cluster)

    # Score clusters
    import math
    cluster_scores = []
    for cluster in clusters:
        avg_score = sum(all_candidates[cid].get("best_vector_score", 0) for cid in cluster) / len(cluster)
        score = avg_score * math.log2(len(cluster) + 1)
        cluster_scores.append((score, cluster))

    # Return sorted clusters
    cluster_scores.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in cluster_scores]

def extract_subtopics(collection, topic_name: str, where_clause: dict) -> list[str]:
    """Automated Diversity Phase: fetch intro + coverage chunks, extract subtopics via LLM."""
    try:
        result = collection.get(where=where_clause, include=["documents"])
        docs = result.get("documents", [])
        if not docs:
            return []
        
        intro = docs[:8]
        coverage = []
        if len(docs) > 8:
            step = max(1, (len(docs) - 8) // 6)
            coverage = docs[8::step][:6]
            
        combined = "\n\n".join(intro + coverage)[:10000]  # Cap length for LLM
        
        prompt = f"Identify 8-12 distinct, specific clinical/technical sub-topics from the following text chunks for the topic '{topic_name}'. Return ONLY a comma-separated list.\n\n{combined}"
        
        payload = {
            "model": "phi4-mini:latest",
            "prompt": prompt,
            "stream": False,
            "temperature": 0.3
        }
        resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=20)
        if resp.status_code == 200:
            text = resp.json().get("response", "")
            return [t.strip().strip("-*") for t in text.split(",") if len(t.strip()) > 3][:12]
        return []
    except Exception as e:
        print(f"[RAG Subtopics] Error: {e}")
        return []


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
) -> tuple[list[str], list[str], list[list[float]], list[float], list[dict]]:
    """
    Perform ChromaDB vector retrieval for a single query.
    Returns: (documents, ids, embeddings, distances, metadatas)
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
        meta_result = results.get("metadatas")
        
        docs = list(docs_result[0]) if docs_result is not None and len(docs_result) > 0 else []
        ids = list(ids_result[0]) if ids_result is not None and len(ids_result) > 0 else []
        embs = list(embs_result[0]) if embs_result is not None and len(embs_result) > 0 else []
        dists = list(dist_result[0]) if dist_result is not None and len(dist_result) > 0 else []
        metas = list(meta_result[0]) if meta_result is not None and len(meta_result) > 0 else []
        
        return docs, ids, embs, dists, metas
    except Exception as e:
        print(f"[RAG-V2] Vector retrieval error: {e}")
        return [], [], [], [], []


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
    chunk_usage_penalty: float = 0.4,
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
    
    where_clause = None
    if topic_id:
        where_clause = {"topic_id": str(topic_id)}
    elif unit_id:
        where_clause = {"unit_id": str(unit_id)}
        
    # --- Automated Diversity Phase (Subtopic Extraction) ---
    subtopics = extract_subtopics(collection, topic_name, where_clause)
    if subtopics:
        print(f"[RAG-V2] Extracted {len(subtopics)} Subtopics for diverse search: {subtopics[:5]}")
        subtopic_variants = [QueryVariant(text=st, strategy="subtopic", weight=0.8) for st in subtopics]
        variants.extend(subtopic_variants)
    
    # Collect candidates across all query variants
    all_candidates = {}  # chunk_id -> {doc, embedding, best_vector_score}
    
    for variant in variants:
        # Try scoped retrieval first
        docs, ids, embs, dists, metas = _vector_retrieve(
            collection, variant.text, fetch_k, where_clause
        )
        
        # Fallback to subject-wide if scoped returns nothing
        if len(docs) == 0 and where_clause is not None:
            docs, ids, embs, dists, metas = _vector_retrieve(
                collection, variant.text, fetch_k, None
            )
        
        scores = _distances_to_scores(dists)
        
        for i, chunk_id in enumerate(ids):
            # NOISE FILTER
            if _is_noisy_chunk(docs[i]):
                continue
                
            weighted_score = scores[i] * variant.weight if i < len(scores) else 0.0
            meta = metas[i] if i < len(metas) else {}
            
            if chunk_id not in all_candidates:
                all_candidates[chunk_id] = {
                    "doc": docs[i],
                    "embedding": embs[i] if i < len(embs) else None,
                    "best_vector_score": weighted_score,
                    "variant_hits": 1,
                    # NEW: locality metadata
                    "page_start": int(meta.get("page_start", 0)) if meta else 0,
                    "page_end": int(meta.get("page_end", 0)) if meta else 0,
                    "chunk_index": int(meta.get("chunk_index", 0)) if meta else 0,
                    "material_id": meta.get("material_id", "") if meta else "",
                    "section_heading": meta.get("section_heading", "") if meta else "",
                }
            else:
                # Keep the best score + count how many variants found this chunk
                existing = all_candidates[chunk_id]
                existing["best_vector_score"] = max(existing["best_vector_score"], weighted_score)
                existing["variant_hits"] += 1
                
    # Filter noise
    clean_candidates = {
        cid: data for cid, data in all_candidates.items()
        if not _is_noisy_chunk(data["doc"])
    }
    if len(clean_candidates) >= n_results:
        all_candidates = clean_candidates
    
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
                
                cached_ce_scores = []
                pairs_to_score = []
                for p in pairs:
                    cached_score = _redis.get_ce_score(p[0], p[1])
                    if cached_score is not None:
                        cached_ce_scores.append(cached_score)
                    else:
                        cached_ce_scores.append(None)
                        pairs_to_score.append(p)
                        
                ce_scores = []
                if pairs_to_score:
                    new_scores = cross_encoder.predict(pairs_to_score)
                    _redis.set_ce_scores_batch(
                        pairs_to_score[0][0], 
                        [p[1] for p in pairs_to_score], 
                        [float(s) for s in new_scores]
                    )
                    
                    new_idx = 0
                    for s in cached_ce_scores:
                        if s is not None:
                            ce_scores.append(s)
                        else:
                            ce_scores.append(new_scores[new_idx])
                            new_idx += 1
                else:
                    ce_scores = cached_ce_scores
                    
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
        # MMR Re-ranking with diversity lambda_mult=0.4
        if len(valid_embs) > n_results:
            query_embedding = cached_embedding_fn(variants[0].text)
            final_docs, final_ids = _mmr_rerank(
                query_embedding, valid_embs, valid_docs, k=n_results, lambda_mult=0.4, doc_ids=valid_ids
            )
        else:
            final_docs = valid_docs
            final_ids = valid_ids
    else:
        # Fallback: just take top ranked
        final_docs = [all_candidates[r[0]]["doc"] for r in ranked[:n_results]]
        final_ids = [r[0] for r in ranked[:n_results]]
    
    # ─── Step 8: Coherence Enforcement ───
    # If chunks span too many different page ranges, constrain to best cluster

    if len(final_ids) > 3:
        clusters = _cluster_by_proximity(final_ids, all_candidates, max_page_gap=5)
        
        if clusters and len(clusters[0]) >= 3:
            # Use the best cluster as primary context
            primary_cluster = clusters[0]
            
            # Fill remaining slots from other clusters (but cap at 2 extras)
            secondary = [cid for c in clusters[1:] for cid in c][:2]
            
            final_ids = primary_cluster + secondary
            final_docs = [all_candidates[cid]["doc"] for cid in final_ids]

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
        "chunk_metadata": {
            cid: {
                "page_start": all_candidates[cid].get("page_start", 0),
                "page_end": all_candidates[cid].get("page_end", 0),
                "section_heading": all_candidates[cid].get("section_heading", ""),
                "material_id": all_candidates[cid].get("material_id", ""),
                "chunk_index": all_candidates[cid].get("chunk_index", 0),
            }
            for cid in final_ids
            if cid in all_candidates
        },
    }
