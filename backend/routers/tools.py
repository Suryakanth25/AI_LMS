from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import os

from database import get_db, SessionLocal
from models import Subject, StudyMaterial, Topic
from services import rag

router = APIRouter(prefix="/api/tools", tags=["tools"])

async def run_reindex(subject_id: int):
    """Background task to re-index all materials for a subject."""
    db = SessionLocal()
    try:
        materials = db.query(StudyMaterial).filter(StudyMaterial.subject_id == subject_id).all()
        print(f"TOOLS: Starting re-index for Subject {subject_id} ({len(materials)} files)")
        
        for mat in materials:
            if not mat.file_path or not os.path.exists(mat.file_path):
                print(f"TOOLS: Skipping {mat.filename} - file not found at {mat.file_path}")
                continue
            
            # Extract and chunk again
            ext = mat.file_type or mat.filename.rsplit(".", 1)[-1].lower() if "." in mat.filename else "txt"
            text = rag.extract_text(mat.file_path, ext)
            chunks = rag.chunk_text(text)
            
            # Re-infer Unit ID if missing
            unit_id = mat.unit_id
            if mat.topic_id and not unit_id:
                topic = db.query(Topic).filter(Topic.id == mat.topic_id).first()
                if topic:
                    unit_id = topic.unit_id
                    mat.unit_id = unit_id
                    db.commit()

            # Delete old chunks
            rag.delete_material_chunks(subject_id, mat.id)
            
            # Ingest with new hierarchical metadata
            rag.ingest(
                subject_id=subject_id,
                material_id=mat.id,
                chunks=chunks,
                unit_id=unit_id,
                topic_id=mat.topic_id,
                source=mat.filename
            )
            print(f"TOOLS: Re-indexed {mat.filename}")

        print(f"TOOLS: Re-index complete for Subject {subject_id}")
    except Exception as e:
        print(f"TOOLS ERROR during re-index: {e}")
    finally:
        db.close()

@router.post("/reindex-subject/{subject_id}")
async def reindex_subject(
    subject_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    background_tasks.add_task(run_reindex, subject_id)
    return {"message": f"Re-indexing started for subject {subject_id}"}
