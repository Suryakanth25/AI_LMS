"""
RAG Indexer v2 — Enhanced chunking with metadata extraction and stable IDs.
Replaces the basic chunking/ingestion in rag.py with richer chunk metadata.
"""
import hashlib
import re
import math
from collections import Counter

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Reuse the shared ChromaDB client and embedding function from rag.py
from services.rag import client, embedding_fn, _get_collection, extract_text


# ─── Metadata Extraction ───

def _has_definition(text: str) -> bool:
    """Detect if chunk contains a definition-like sentence."""
    patterns = [
        r'\bis defined as\b', r'\brefers to\b', r'\bis known as\b',
        r'\bmeans\b', r'\bis a\b', r'\bare\b.*\bthat\b',
        r'\bcan be described as\b', r'\bis characterized by\b',
    ]
    lower = text.lower()
    return any(re.search(p, lower) for p in patterns)


def _has_list(text: str) -> bool:
    """Detect if chunk contains a list or enumeration."""
    # Numbered lists: 1. 2. 3. or (a) (b) (c) or i) ii) iii)
    numbered = len(re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s|[a-z][\.\)]\s|\([a-z]\)\s|[ivx]+[\.\)]\s)', text))
    # Bullet points
    bullets = len(re.findall(r'(?:^|\n)\s*[-•●▪]\s', text))
    return (numbered >= 2) or (bullets >= 2)


def _has_math(text: str) -> bool:
    """Detect if chunk contains mathematical formulas or equations."""
    patterns = [
        r'[=<>≤≥±∓∞∑∏∫√]',  # Math symbols
        r'\b\d+\s*[×÷/\*\+\-]\s*\d+',  # Arithmetic
        r'[a-zA-Z]\s*=\s*[a-zA-Z0-9]',  # Variable assignment
        r'\b(?:formula|equation|calculate|compute)\b',
    ]
    return any(re.search(p, text) for p in patterns)


def _has_code(text: str) -> bool:
    """Detect if chunk contains code-like content."""
    patterns = [
        r'(?:def |class |import |from .+ import)',  # Python
        r'(?:function |const |let |var |=>)',  # JavaScript
        r'(?:\{[^}]*:[^}]*\})',  # JSON-like
        r'(?:SELECT |FROM |WHERE |INSERT )',  # SQL
    ]
    return any(re.search(p, text) for p in patterns)


def _estimate_complexity(text: str) -> str:
    """Estimate content complexity: low / medium / high."""
    words = text.split()
    word_count = len(words)
    
    # Avg word length
    avg_word_len = sum(len(w) for w in words) / max(word_count, 1)
    
    # Sentence count (rough)
    sentences = re.split(r'[.!?]+', text)
    sentence_count = len([s for s in sentences if s.strip()])
    
    # Avg sentence length
    avg_sent_len = word_count / max(sentence_count, 1)
    
    # Score: long words + long sentences + technical terms = higher complexity
    technical_markers = len(re.findall(r'\b[A-Z]{2,}\b', text))  # Acronyms
    has_math_content = _has_math(text)
    
    score = 0
    if avg_word_len > 6: score += 1
    if avg_sent_len > 25: score += 1
    if technical_markers > 2: score += 1
    if has_math_content: score += 1
    if word_count > 200: score += 1
    
    if score >= 3:
        return "high"
    elif score >= 1:
        return "medium"
    return "low"


def _extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """Extract top-N keywords using simple TF heuristic (no external deps)."""
    # Stopwords (minimal set)
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'out', 'off', 'over',
        'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
        'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'because', 'but', 'and',
        'or', 'if', 'while', 'about', 'up', 'its', 'it', 'this', 'that',
        'these', 'those', 'he', 'she', 'they', 'we', 'you', 'i', 'my', 'your',
        'his', 'her', 'their', 'our', 'which', 'who', 'whom', 'what',
        'also', 'however', 'although', 'therefore', 'thus', 'hence',
    }
    
    # Tokenize: only keep alphabetic words 3+ chars
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    words = [w for w in words if w not in stopwords]
    
    counts = Counter(words)
    return [word for word, _ in counts.most_common(top_n)]


def _make_stable_chunk_id(material_id: int, chunk_text: str) -> str:
    """Generate a stable, deterministic chunk ID from material_id + normalized text."""
    normalized = chunk_text.lower().strip()
    content = f"{material_id}:{normalized}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _make_chunk_hash(chunk_text: str) -> str:
    """Generate a hash for dedup across uploads."""
    normalized = chunk_text.lower().strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ─── Enhanced Chunking ───

def enhanced_chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Enhanced chunking with larger windows for richer context.
    Uses RecursiveCharacterTextSplitter with SHA-256 dedup.
    """
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
        h = _make_chunk_hash(chunk)
        if h not in seen:
            seen.add(h)
            unique_chunks.append(chunk)

    return unique_chunks


# ─── Enhanced Ingestion ───

def enhanced_ingest(
    subject_id: int,
    material_id: int,
    text: str,
    unit_id: int = None,
    topic_id: int = None,
    source: str = "unknown",
    chunk_size: int = 1000,
    overlap: int = 200,
) -> tuple[str, int]:
    """
    Enhanced ingestion with metadata extraction and stable chunk IDs.
    
    Returns: (collection_name, chunk_count)
    """
    collection_name = f"subject_{subject_id}"
    collection = _get_collection(collection_name)
    
    # Chunk the text
    chunks = enhanced_chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    
    if not chunks:
        return (collection_name, 0)
    
    # Build IDs, documents, and metadata
    batch_size = 5000
    total_chunks = len(chunks)
    
    for start in range(0, total_chunks, batch_size):
        end = min(start + batch_size, total_chunks)
        batch_chunks = chunks[start:end]
        
        ids = []
        metadatas = []
        
        for chunk in batch_chunks:
            chunk_id = _make_stable_chunk_id(material_id, chunk)
            chunk_hash = _make_chunk_hash(chunk)
            keywords = _extract_keywords(chunk, top_n=5)
            
            ids.append(chunk_id)
            metadatas.append({
                "source": str(source),
                "subject_id": str(subject_id),
                "unit_id": str(unit_id) if unit_id is not None else "0",
                "topic_id": str(topic_id) if topic_id is not None else "0",
                "type": "textbook",
                "chunk_hash": chunk_hash,
                "has_definition": str(_has_definition(chunk)),
                "has_list": str(_has_list(chunk)),
                "has_math": str(_has_math(chunk)),
                "has_code": str(_has_code(chunk)),
                "estimated_complexity": _estimate_complexity(chunk),
                "keywords": ",".join(keywords),
            })
        
        # Upsert to handle re-uploads gracefully
        collection.upsert(
            documents=batch_chunks,
            ids=ids,
            metadatas=metadatas,
        )
    
    return (collection_name, total_chunks)
