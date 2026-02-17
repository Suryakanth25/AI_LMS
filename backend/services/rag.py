import chromadb
import PyPDF2
from docx import Document
import os

# ChromaDB persistent client
client = chromadb.PersistentClient(path="./chromadb_data")


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


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by sentence boundaries."""
    sentences = text.split(". ")
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Start new chunk with overlap from end of previous
            current_chunk = current_chunk[-overlap:] + " " + sentence
        else:
            current_chunk = current_chunk + ". " + sentence if current_chunk else sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def ingest(subject_id: int, material_id: int, chunks: list[str], unit_id: int = None, topic_id: int = None, source: str = "unknown") -> tuple[str, int]:
    """Ingest text chunks into ChromaDB collection for a subject."""
    collection_name = f"subject_{subject_id}"
    collection = client.get_or_create_collection(name=collection_name)

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
                "type": "textbook" # Optional: could be dynamic
            }
            for i in range(start, end)
        ]

        collection.add(
            documents=batch_chunks,
            ids=ids,
            metadatas=metadatas,
        )

    return (collection_name, total_chunks)


def retrieve(subject_id: int, query: str, n_results: int = 5, unit_id: int = None, topic_id: int = None, unit_name: str = None) -> list[str]:
    """
    Retrieve relevant chunks from ChromaDB.
    Task 2: Hybrid Scope Retrieval with Fallback.
    Task 4: Basic Diversity Filtering.
    """
    collection_name = f"subject_{subject_id}"
    try:
        collection = client.get_collection(name=collection_name)
        if collection.count() == 0:
            return []
        
        # Step 1: Scoped Search (Try Unit/Topic first)
        where_clause = None
        if topic_id:
            where_clause = {"topic_id": str(topic_id)}
        elif unit_id:
            where_clause = {"unit_id": str(unit_id)}

        results = collection.query(
            query_texts=[query],
            n_results=n_results * 2, # Fetch more for diversity filtering
            where=where_clause
        )
        
        relevant_chunks = results["documents"][0] if results and results["documents"] else []

        # Step 2: Fallback Action (Risk A Fix)
        if not relevant_chunks and (unit_id or topic_id):
            print(f"RAG: Scoped search for Unit {unit_id}/Topic {topic_id} failed. Falling back to subject-wide search.")
            # Unfiltered query
            results = collection.query(
                query_texts=[query],
                n_results=n_results * 4
            )
            raw_chunks = results["documents"][0] if results and results["documents"] else []
            
            # Keyword Filtering (simple text matching) if unit_name provided
            if unit_name and raw_chunks:
                keywords = unit_name.lower().split()
                # Keep chunks containing at least one keyword from unit name
                filtered = [c for c in raw_chunks if any(k in c.lower() for k in keywords)]
                relevant_chunks = filtered if filtered else raw_chunks
            else:
                relevant_chunks = raw_chunks

        # Step 4: Diversity & De-Duplication Logic
        # (MMR Lite: Simple similarity check to avoid adjacent identical chunks)
        unique_chunks = []
        for chunk in relevant_chunks:
            is_too_similar = False
            for existing in unique_chunks:
                # Basic overlap check
                if chunk[:100] == existing[:100] or chunk[-100:] == existing[-100:]:
                    is_too_similar = True
                    break
            if not is_too_similar:
                unique_chunks.append(chunk)
            
            if len(unique_chunks) >= n_results:
                break
                
        return unique_chunks

    except Exception as e:
        print(f"RAG Retrieval Error: {e}")
        return []


def get_stats(subject_id: int) -> dict:
    """Get ChromaDB stats for a subject collection."""
    collection_name = f"subject_{subject_id}"
    try:
        collection = client.get_collection(name=collection_name)
        return {"collection": collection_name, "total_chunks": collection.count()}
    except Exception:
        return {"collection": collection_name, "total_chunks": 0}


def delete_material_chunks(subject_id: int, material_id: int):
    """Delete all chunks belonging to a specific material from ChromaDB."""
    collection_name = f"subject_{subject_id}"
    try:
        collection = client.get_collection(name=collection_name)
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
