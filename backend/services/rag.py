import chromadb
import PyPDF2
from docx import Document
import os
import hashlib
import numpy as np

# Force offline mode — the model is already cached locally.
# This prevents startup crashes when HuggingFace Hub is unreachable.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# ─── Embedding Function ───
# Use sentence-transformers/all-MiniLM-L6-v2 for semantic embeddings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
embedding_fn = SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# ChromaDB persistent client
client = chromadb.PersistentClient(path="./chromadb_data")


def _get_collection(name: str):
    """Get or create a collection with the sentence-transformer embedding function."""
    return client.get_or_create_collection(
        name=name,
        embedding_function=embedding_fn,
    )


def extract_text(file_path: str, file_type: str) -> str:
    """Extract text from PDF, DOCX, or TXT files."""
    if file_type == "pdf":
        text_parts = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    elif file_type == "docx":
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    elif file_type == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    return ""


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    """
    Smart chunking using LangChain's RecursiveCharacterTextSplitter.
    Splits on paragraphs → sentences → words, preserving context boundaries.
    Includes SHA-256 deduplication to remove identical chunks.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks = splitter.split_text(text)

    # SHA-256 deduplication
    seen = set()
    unique_chunks = []
    for chunk in raw_chunks:
        h = hashlib.sha256(chunk.lower().strip().encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique_chunks.append(chunk)

    return unique_chunks


def ingest(subject_id: int, material_id: int, chunks: list[str], unit_id: int = None, topic_id: int = None, source: str = "unknown") -> tuple[str, int]:
    """Ingest text chunks into ChromaDB collection for a subject."""
    collection_name = f"subject_{subject_id}"
    collection = _get_collection(collection_name)

    # Use batch processing
    batch_size = 5000
    total_chunks = len(chunks)

    for start in range(0, total_chunks, batch_size):
        end = min(start + batch_size, total_chunks)
        batch_chunks = chunks[start:end]
        
        ids = [f"mat_{material_id}_chunk_{i}" for i in range(start, end)]
        metadatas = [
            {
                "source": str(source),
                "subject_id": str(subject_id),
                "unit_id": str(unit_id) if unit_id is not None else "0",
                "topic_id": str(topic_id) if topic_id is not None else "0",
                "type": "textbook"
            }
            for i in range(start, end)
        ]

        collection.add(
            documents=batch_chunks,
            ids=ids,
            metadatas=metadatas,
        )

    return (collection_name, total_chunks)


def _mmr_rerank(query_embedding: list[float], doc_embeddings: list[list[float]], documents: list[str], k: int = 5, lambda_mult: float = 0.7) -> list[str]:
    """
    Maximal Marginal Relevance (MMR) re-ranking.
    Balances relevance to the query with diversity among selected documents.
    
    lambda_mult: 0.0 = max diversity, 1.0 = max relevance
    """
    if not documents:
        return []

    query_vec = np.array(query_embedding)
    doc_vecs = np.array(doc_embeddings)

    # Cosine similarity: query vs all docs
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    doc_norms = doc_vecs / (np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-10)
    query_similarities = doc_norms @ query_norm

    selected_indices = []
    remaining = list(range(len(documents)))

    for _ in range(min(k, len(documents))):
        if not remaining:
            break

        mmr_scores = []
        for idx in remaining:
            relevance = float(query_similarities[idx])

            # Max similarity to already selected docs
            if selected_indices:
                selected_vecs = doc_norms[selected_indices]
                redundancy = float(max(float(doc_norms[idx] @ sv) for sv in selected_vecs))
            else:
                redundancy = 0.0

            mmr = lambda_mult * relevance - (1 - lambda_mult) * redundancy
            mmr_scores.append((idx, float(mmr)))

        # Pick the one with highest MMR score
        best_idx = max(mmr_scores, key=lambda x: x[1])[0]
        selected_indices.append(best_idx)
        remaining.remove(best_idx)

    return [documents[i] for i in selected_indices]


def retrieve(subject_id: int, query: str, n_results: int = 5, unit_id: int = None, topic_id: int = None, unit_name: str = None) -> list[str]:
    """
    Retrieve relevant chunks using MMR (Maximal Marginal Relevance).
    Stage 1: Scoped search by unit/topic with fallback.
    Stage 2: MMR re-ranking for diverse, non-redundant results.
    """
    collection_name = f"subject_{subject_id}"
    try:
        collection = _get_collection(collection_name)
        if collection.count() == 0:
            return []
        
        fetch_k = max(n_results * 6, 30)  # Fetch many candidates for MMR

        # Step 1: Scoped Search (Try Unit/Topic first)
        where_clause = None
        if topic_id:
            where_clause = {"topic_id": str(topic_id)}
        elif unit_id:
            where_clause = {"unit_id": str(unit_id)}

        results = collection.query(
            query_texts=[query],
            n_results=fetch_k,
            where=where_clause,
            include=["documents", "embeddings"],
        )
        
        # Safe extraction: use 'is not None' and len() checks instead of truthiness
        # (ChromaDB 1.5.x returns numpy arrays which fail Python truthiness checks)
        docs_result = results.get("documents") if results else None
        embs_result = results.get("embeddings") if results else None
        raw_docs = list(docs_result[0]) if docs_result is not None and len(docs_result) > 0 else []
        raw_embeddings = list(embs_result[0]) if embs_result is not None and len(embs_result) > 0 else []

        # Step 2: Fallback (if scoped search returns nothing)
        if len(raw_docs) == 0 and (unit_id or topic_id):
            print(f"RAG: Scoped search for Unit {unit_id}/Topic {topic_id} failed. Falling back to subject-wide search.")
            results = collection.query(
                query_texts=[query],
                n_results=fetch_k,
                include=["documents", "embeddings"],
            )
            docs_result = results.get("documents") if results else None
            embs_result = results.get("embeddings") if results else None
            raw_docs = list(docs_result[0]) if docs_result is not None and len(docs_result) > 0 else []
            raw_embeddings = list(embs_result[0]) if embs_result is not None and len(embs_result) > 0 else []
            
            # Keyword filtering if unit_name provided
            if unit_name and len(raw_docs) > 0:
                keywords = unit_name.lower().split()
                filtered_pairs = [
                    (doc, emb) for doc, emb in zip(raw_docs, raw_embeddings)
                    if any(k in doc.lower() for k in keywords)
                ]
                if filtered_pairs:
                    raw_docs, raw_embeddings = zip(*filtered_pairs)
                    raw_docs = list(raw_docs)
                    raw_embeddings = list(raw_embeddings)

        if len(raw_docs) == 0:
            return []

        # Step 3: MMR Re-ranking for diversity
        if len(raw_embeddings) > 0:
            query_embedding = embedding_fn([query])[0]
            return _mmr_rerank(query_embedding, raw_embeddings, raw_docs, k=n_results, lambda_mult=0.7)
        else:
            # Fallback: simple dedup if embeddings aren't available
            unique = []
            for doc in raw_docs:
                if doc not in unique:
                    unique.append(doc)
                if len(unique) >= n_results:
                    break
            return unique

    except Exception as e:
        print(f"RAG Retrieval Error: {e}")
        return []


def get_stats(subject_id: int) -> dict:
    """Get ChromaDB stats for a subject collection."""
    collection_name = f"subject_{subject_id}"
    try:
        collection = _get_collection(collection_name)
        return {"collection": collection_name, "total_chunks": collection.count()}
    except Exception:
        return {"collection": collection_name, "total_chunks": 0}


def delete_material_chunks(subject_id: int, material_id: int):
    """Delete all chunks belonging to a specific material from ChromaDB."""
    collection_name = f"subject_{subject_id}"
    try:
        collection = _get_collection(collection_name)
        # Get all IDs, filter by prefix
        all_data = collection.get()
        ids_to_delete = [
            id_ for id_ in all_data["ids"]
            if id_.startswith(f"mat_{material_id}_")
        ]
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
    except Exception:
        pass


# ─── V2 Delegation APIs (backward compatible) ───

def ingest_enhanced(subject_id: int, material_id: int, text: str, unit_id=None, topic_id=None, source="unknown"):
    """Delegate to the enhanced rag_indexer for richer chunking + metadata."""
    from services.rag_indexer import enhanced_ingest
    return enhanced_ingest(subject_id, material_id, text, unit_id, topic_id, source)


def retrieve_context_for_generation(**kwargs):
    """Delegate to the hybrid retriever pipeline."""
    from services.rag_retriever import retrieve_context_for_generation as _retrieve
    return _retrieve(**kwargs)
