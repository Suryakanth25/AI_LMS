from services.rag import embedding_fn
from services.redis_cache import RedisCache

_cache = RedisCache()

def cached_embedding_fn(text: str) -> list[float]:
    cached = _cache.get_embedding(text)
    if cached is not None:
        return cached
    embedding = embedding_fn([text])[0]
    _cache.set_embedding(text, embedding)
    return embedding

def cached_embedding_fn_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    cached_results = _cache.get_embeddings_batch(texts)
    
    # Identify which entries missed
    miss_indices = [i for i, res in enumerate(cached_results) if res is None]
    if not miss_indices:
        return cached_results

    # Compute missing
    miss_texts = [texts[i] for i in miss_indices]
    computed_embs = embedding_fn(miss_texts)

    # Cache and fill results
    to_cache = {}
    for i, idx in enumerate(miss_indices):
        emb = computed_embs[i]
        to_cache[miss_texts[i]] = emb
        cached_results[idx] = emb
        
    _cache.set_embeddings_batch(to_cache)
    
    return cached_results
