"""
RAG Indexer v2 — Enhanced chunking with metadata extraction and stable IDs.
Replaces the basic chunking/ingestion in rag.py with richer chunk metadata.
"""
import hashlib
import re
import math
from collections import Counter

import PyPDF2
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Reuse the shared ChromaDB client and embedding function from rag.py
from services.rag import client, embedding_fn, _get_collection, extract_text


def extract_text_with_pages(file_path: str, file_type: str) -> tuple[str, list[tuple[int, int]]]:
    """Extract text and character offsets per page."""
    text_parts = []
    page_map = []  # list of (start_char, end_char)
    current_length = 0
    
    if file_type == "pdf":
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    start = current_length
                    text_parts.append(page_text)
                    current_length += len(page_text)
                    text_parts.append("\n")
                    current_length += 1
                    page_map.append((start, current_length - 1))
                else:
                    page_map.append((current_length, current_length))
        return "".join(text_parts), page_map

    elif file_type == "docx":
        doc = Document(file_path)
        for p in doc.paragraphs:
            if p.text.strip():
                start = current_length
                text_parts.append(p.text)
                current_length += len(p.text)
                text_parts.append("\n")
                current_length += 1
        return "".join(text_parts), [(0, current_length)]

    elif file_type == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
            return text, [(0, len(text))]

    return "", []



def strip_boilerplate(text: str) -> str:
    """Stage 1 Noise Filtering: Remove publisher info, copyright, ISBNs, and TOC."""
    # Remove ISBNs
    text = re.sub(r'ISBN(?:-1[03])?:?\s*(?=[0-9X]{10,13})[-0-9X]+', '', text, flags=re.IGNORECASE)
    # Remove copyright lines
    text = re.sub(r'©.*?(?=\n|$)', '', text)
    text = re.sub(r'Copyright.*?(?=\n|$)', '', text, flags=re.IGNORECASE)
    # Remove Tables of Contents lines like "...12" or "... 12"
    text = re.sub(r'^(.*?)\.{3,}\s*\d+\s*$', '', text, flags=re.MULTILINE)
    return text


def snap_to_sentence(chunk: str) -> str:
    """Trim leading and trailing partial sentences so every chunk starts and ends cleanly."""
    chunk = chunk.strip()
    if not chunk:
        return chunk
    
    # Drop leading partial sentence (before the first period/punctuation followed by a capital letter)
    if chunk[0].islower() or not chunk[0].isalnum():
        match = re.search(r'[.!?]\s+([A-Z])', chunk)
        if match:
            chunk = chunk[match.start(1):]
            
    # Drop trailing partial sentence
    if not re.search(r'[.!?]["\']?\s*$', chunk):
        matches = list(re.finditer(r'[.!?]["\']?(?=\s|$)', chunk))
        if matches:
            last_match = matches[-1]
            chunk = chunk[:last_match.end()]
            
    return chunk.strip()


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

def enhanced_chunk_text(text: str, chunk_size: int = 2000, overlap: int = 400) -> list[str]:
    """
    Enhanced chunking with larger windows for richer context and sentence snapping.
    Uses RecursiveCharacterTextSplitter with SHA-256 dedup.
    """
    text = strip_boilerplate(text)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks = splitter.split_text(text)

    # SHA-256 deduplication and sentence snapping
    seen = set()
    unique_chunks = []
    for chunk in raw_chunks:
        snapped = snap_to_sentence(chunk)
        if not snapped or len(snapped) < 50:
            continue
            
        h = _make_chunk_hash(snapped)
        if h not in seen:
            seen.add(h)
            unique_chunks.append(snapped)

    return unique_chunks


# ─── Enhanced Ingestion ───

def enhanced_ingest(
    subject_id: int,
    material_id: int,
    text: str,
    unit_id: int = None,
    topic_id: int = None,
    source: str = "unknown",
    chunk_size: int = 2000,
    overlap: int = 400,
    page_map: list[tuple[int, int]] = None,
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
        
        search_idx = 0
        
        for k, chunk in enumerate(batch_chunks):
            # Find start pos of chunk
            start_idx = text.find(chunk[:100], search_idx)
            if start_idx == -1:
                start_idx = search_idx  # fallback
            else:
                search_idx = start_idx
            end_idx = start_idx + len(chunk)

            # Map to pages
            page_start = 1
            page_end = 1
            if page_map:
                for idx_p, (p_start, p_end) in enumerate(page_map):
                    if p_start <= start_idx <= p_end:
                        page_start = idx_p + 1
                    if p_start <= end_idx <= p_end:
                        page_end = idx_p + 1
                if page_end < page_start:
                    page_end = page_start

            # Section heading detection
            text_before = text[:start_idx]
            section_heading = ""
            recent_text = text_before[-3000:]
            matches = list(re.finditer(r'(?m)^(Chapter\s+\d+|UNIT\s+\d+[:\-]?|(?:\d+\.)+\d+\s+[A-Z].*)$', recent_text, re.IGNORECASE))
            if matches:
                section_heading = matches[-1].group(1).strip()[:100]

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
                "page_start": str(page_start),
                "page_end": str(page_end),
                "chunk_index": str(start + k),
                "section_heading": section_heading,
                "material_id": str(material_id),
            })
        
        # Upsert to handle re-uploads gracefully
        collection.upsert(
            documents=batch_chunks,
            ids=ids,
            metadatas=metadatas,
        )
    
    return (collection_name, total_chunks)
