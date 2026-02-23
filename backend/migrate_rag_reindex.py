"""
Migration script: Re-index all existing study materials with the new RAG architecture.
- Uses RecursiveCharacterTextSplitter (400 chars, 80 overlap)
- Uses sentence-transformers/all-MiniLM-L6-v2 embeddings
- SHA-256 deduplication during chunking
"""
import os
import sys
import shutil

# Ensure we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import StudyMaterial
from services import rag


def migrate():
    db = SessionLocal()
    materials = db.query(StudyMaterial).all()

    if not materials:
        print("No materials found in database. Nothing to migrate.")
        db.close()
        return

    print(f"Found {len(materials)} materials to re-index.\n")

    # Step 1: Collect all subject IDs so we can wipe their collections
    subject_ids = set(m.subject_id for m in materials)

    for sid in subject_ids:
        collection_name = f"subject_{sid}"
        try:
            rag.client.delete_collection(name=collection_name)
            print(f"  Deleted old collection: {collection_name}")
        except Exception:
            print(f"  No existing collection: {collection_name} (ok)")

    print()

    # Step 2: Re-ingest each material
    success = 0
    skipped = 0
    errors = 0

    for mat in materials:
        label = f"[Material {mat.id}] {mat.filename}"

        if not mat.file_path or not os.path.exists(mat.file_path):
            print(f"  SKIP {label} - file not found at {mat.file_path}")
            skipped += 1
            continue

        ext = mat.file_type or mat.filename.rsplit(".", 1)[-1].lower()
        try:
            # Extract text
            text = rag.extract_text(mat.file_path, ext)
            if not text or len(text.strip()) < 20:
                print(f"  SKIP {label} - no text extracted")
                skipped += 1
                continue

            # Chunk with new splitter + dedup
            chunks = rag.chunk_text(text)

            # Ingest with new embedding function
            collection_name, chunk_count = rag.ingest(
                subject_id=mat.subject_id,
                material_id=mat.id,
                chunks=chunks,
                unit_id=mat.unit_id,
                topic_id=mat.topic_id,
                source=mat.filename,
            )

            # Update chunk_count in DB
            mat.chunk_count = chunk_count
            mat.chromadb_collection = collection_name
            db.commit()

            print(f"  OK   {label} -> {chunk_count} chunks in {collection_name}")
            success += 1

        except Exception as e:
            print(f"  ERR  {label} - {e}")
            errors += 1

    db.close()

    print(f"\n{'='*50}")
    print(f"Migration complete!")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"{'='*50}")


if __name__ == "__main__":
    migrate()
