import hashlib
import json
import logging
from collections import OrderedDict
try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)

class RedisCache:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisCache, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_cache()
        return cls._instance

    def _init_cache(self):
        self.is_available = False
        self.client = None
        self.l1_cache = OrderedDict()
        self.l1_max_size = 10000
        self.l1_hits = 0
        self.l1_misses = 0

        if redis is None:
            logger.warning("[Redis] Redis python package not installed.")
            return

        try:
            self.client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.client.ping()
            self.is_available = True
            logger.info("[Redis] Connected successfully.")
        except Exception as e:
            logger.warning(f"[Redis] Connection failed: {e}. Falling back to in-memory only (graceful degradation).")

    def _md5(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _update_l1(self, key: str, value):
        self.l1_cache[key] = value
        self.l1_cache.move_to_end(key)
        if len(self.l1_cache) > self.l1_max_size:
            self.l1_cache.popitem(last=False)

    # ─── 1A. Two-Tier Embedding Cache ───

    def get_embedding(self, text: str):
        key = f"emb:{self._md5(text)}"
        
        # L1 check
        if key in self.l1_cache:
            self.l1_hits += 1
            self.l1_cache.move_to_end(key)
            return self.l1_cache[key]
        
        self.l1_misses += 1
        
        # L2 check
        if not self.is_available:
            return None
            
        try:
            cached = self.client.get(key)
            if cached:
                emb = json.loads(cached)
                self._update_l1(key, emb)
                return emb
        except Exception as e:
            logger.warning(f"[Redis] get_embedding failed: {e}")
            
        return None

    def set_embedding(self, text: str, embedding: list[float]):
        key = f"emb:{self._md5(text)}"
        self._update_l1(key, embedding)
        
        if not self.is_available:
            return
            
        try:
            self.client.set(key, json.dumps(embedding), ex=7 * 24 * 3600)
        except Exception as e:
            logger.warning(f"[Redis] set_embedding failed: {e}")

    def get_embeddings_batch(self, texts: list[str]) -> list:
        results = [None] * len(texts)
        if not self.is_available:
            for i, text in enumerate(texts):
                key = f"emb:{self._md5(text)}"
                if key in self.l1_cache:
                    self.l1_hits += 1
                    self.l1_cache.move_to_end(key)
                    results[i] = self.l1_cache[key]
                else:
                    self.l1_misses += 1
            return results

        keys_to_fetch = []
        indices_to_fetch = []
        
        for i, text in enumerate(texts):
            key = f"emb:{self._md5(text)}"
            if key in self.l1_cache:
                self.l1_hits += 1
                self.l1_cache.move_to_end(key)
                results[i] = self.l1_cache[key]
            else:
                self.l1_misses += 1
                keys_to_fetch.append(key)
                indices_to_fetch.append(i)

        if not keys_to_fetch:
            return results

        try:
            cached_vals = self.client.mget(keys_to_fetch)
            for idx, key, val in zip(indices_to_fetch, keys_to_fetch, cached_vals):
                if val:
                    emb = json.loads(val)
                    self._update_l1(key, emb)
                    results[idx] = emb
        except Exception as e:
            logger.warning(f"[Redis] get_embeddings_batch failed: {e}")

        return results

    def set_embeddings_batch(self, emb_dict: dict):
        # emb_dict maps text -> embedding sequence
        if not emb_dict:
            return

        pipeline_data = {}
        for text, emb in emb_dict.items():
            key = f"emb:{self._md5(text)}"
            self._update_l1(key, emb)
            if self.is_available:
                pipeline_data[key] = json.dumps(emb)

        if not self.is_available or not pipeline_data:
            return

        try:
            pipe = self.client.pipeline()
            # 7 days TTl
            ttl = 7 * 24 * 3600
            for key, val in pipeline_data.items():
                pipe.set(key, val, ex=ttl)
            pipe.execute()
        except Exception as e:
            logger.warning(f"[Redis] set_embeddings_batch failed: {e}")

    # ─── 1B. Generation Locks ───

    def acquire_generation_lock(self, subject_id, job_id) -> bool:
        if not self.is_available:
            return True  # Fail-open
        try:
            key = f"lock:gen:{subject_id}"
            acquired = self.client.set(key, str(job_id), nx=True, ex=600)
            return bool(acquired)
        except Exception as e:
            logger.warning(f"[Redis] acquire_generation_lock failed: {e}")
            return True

    def release_generation_lock(self, subject_id):
        if not self.is_available:
            return
        try:
            key = f"lock:gen:{subject_id}"
            self.client.delete(key)
        except Exception as e:
            logger.warning(f"[Redis] release_generation_lock failed: {e}")

    # ─── 1C. Retrieval Result Cache ───

    def get_cached_retrieval(self, subject_id, topic_id, query_text: str):
        if not self.is_available:
            return None
        try:
            tid = topic_id if topic_id else "0"
            key = f"rag:{subject_id}:{tid}:{self._md5(query_text)[:12]}"
            cached = self.client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"[Redis] get_cached_retrieval failed: {e}")
        return None

    def cache_retrieval(self, subject_id, topic_id, query_text: str, chunks: list[str], chunk_ids: list[str]):
        if not self.is_available:
            return
        try:
            tid = topic_id if topic_id else "0"
            key = f"rag:{subject_id}:{tid}:{self._md5(query_text)[:12]}"
            val = json.dumps({"chunks": chunks, "chunk_ids": chunk_ids})
            self.client.set(key, val, ex=3600) # 1 hour TTL
        except Exception as e:
            logger.warning(f"[Redis] cache_retrieval failed: {e}")

    def invalidate_retrieval_cache(self, subject_id):
        if not self.is_available:
            return
        try:
            pattern = f"rag:{subject_id}:*"
            cursor = '0'
            while cursor != 0:
                cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    self.client.delete(*keys)
        except Exception as e:
            logger.warning(f"[Redis] invalidate_retrieval_cache failed: {e}")

    # ─── 1D. Novelty / Question Dedup Cache ───

    def add_question_embedding(self, subject_id, topic_id, question_id, embedding: list[float]):
        if not self.is_available:
            return
        try:
            key = f"qemb:{subject_id}:{topic_id}:{question_id}"
            self.client.set(key, json.dumps(embedding), ex=30 * 24 * 3600) # 30 days
        except Exception as e:
            logger.warning(f"[Redis] add_question_embedding failed: {e}")

    def get_question_embeddings(self, subject_id, topic_id) -> list:
        if not self.is_available:
            return []
        try:
            pattern = f"qemb:{subject_id}:{topic_id}:*"
            embs = []
            cursor = '0'
            while cursor != 0:
                cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    vals = self.client.mget(keys)
                    for val in vals:
                        if val:
                            embs.append(json.loads(val))
            return embs
        except Exception as e:
            logger.warning(f"[Redis] get_question_embeddings failed: {e}")
            return []

    # ─── 1E. Cross-Encoder Score Cache ───

    def get_ce_score(self, query: str, doc: str):
        if not self.is_available:
            return None
        try:
            key = f"ce:{self._md5(query + '|||' + doc)}"
            val = self.client.get(key)
            if val is not None:
                return float(val)
        except Exception as e:
            logger.warning(f"[Redis] get_ce_score failed: {e}")
        return None

    def set_ce_scores_batch(self, query: str, docs: list[str], scores: list[float]):
        if not self.is_available or not docs:
            return
        try:
            pipe = self.client.pipeline()
            ttl = 24 * 3600 # 1 day TTL
            for doc, score in zip(docs, scores):
                key = f"ce:{self._md5(query + '|||' + doc)}"
                pipe.set(key, str(score), ex=ttl)
            pipe.execute()
        except Exception as e:
            logger.warning(f"[Redis] set_ce_scores_batch failed: {e}")

    # ─── 1G. Stats Endpoint ───

    def get_stats(self) -> dict:
        total_requests = self.l1_hits + self.l1_misses
        hit_rate = (self.l1_hits / total_requests) if total_requests > 0 else 0.0
        
        mem_used = "unknown"
        if self.is_available:
            try:
                info = self.client.info(section='memory')
                mem_used = info.get('used_memory_human', 'unknown')
            except:
                pass

        return {
            "redis_available": self.is_available,
            "l1_size": len(self.l1_cache),
            "l1_hit_rate": hit_rate,
            "redis_memory_used": mem_used
        }
