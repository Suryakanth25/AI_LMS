import os
import time
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, Request
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, List

from database import get_db
from models import Subject, Unit, Topic, StudyMaterial
from schemas import (
    SubjectCreate, SubjectResponse, SubjectDetail,
    UnitCreate, UnitResponse,
    TopicCreate, TopicResponse,
    MaterialResponse,
)
from services import rag

router = APIRouter(prefix="/api", tags=["subjects"])


# --- Subjects CRUD ---

@router.get("/subjects/", response_model=list[SubjectResponse])
def list_subjects(db: Session = Depends(get_db)):
    subjects = db.query(Subject).all()
    result = []
    for s in subjects:
        unit_count = len(s.units)
        topic_count = sum(len(u.topics) for u in s.units)
        material_count = len(s.materials)
        result.append(SubjectResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            created_at=s.created_at,
            unit_count=unit_count,
            topic_count=topic_count,
            material_count=material_count,
        ))
    return result


@router.get("/subjects/{subject_id}")
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Fetch Subject-level COs
    # Re-using schemas.COResponse structure
    cos_data = []
    for co in subject.course_outcomes:
        cos_data.append({
            "id": co.id,
            "description": co.description, # Renamed
            "code": co.code,
            "subject_id": co.subject_id,
            "blooms_level": co.blooms_level,
            "blooms_levels": co.blooms_levels,
            "created_at": str(co.created_at)
        })

    units_data = []
    for u in subject.units:
        topics_data = []
        for t in u.topics:
            sq_count = len(t.sample_questions)
            topics_data.append({
                "id": t.id, 
                "title": t.title, 
                "unit_id": t.unit_id, 
                "created_at": str(t.created_at),
                "syllabus_data": t.syllabus_data or {},
                "sample_questions_count": sq_count,
                 # COs are no longer on topics
                 "bloom_distribution": (t.syllabus_data or {}).get("bloom_distribution")
            })
            
        # LOs
        los_data = []
        for lo in u.learning_outcomes:
             los_data.append({
                "id": lo.id, 
                "description": lo.description, # Renamed
                "code": lo.code, 
                "unit_id": lo.unit_id, 
                "created_at": str(lo.created_at)
             })
        
        # Mapped COs
        mapped_cos_data = []
        for mapping in u.co_mappings:
             co = mapping.course_outcome
             if co:
                 mapped_cos_data.append({
                    "id": co.id,
                    "description": co.description,
                    "code": co.code,
                    "subject_id": co.subject_id,
                    "blooms_level": co.blooms_level,
                    "blooms_levels": co.blooms_levels,
                    "created_at": str(co.created_at)
                 })

        units_data.append({
            "id": u.id,
            "name": u.name,
            "unit_number": u.unit_number,
            "subject_id": u.subject_id,
            "created_at": str(u.created_at),
            "topics": topics_data,
            "learning_outcomes": los_data,
            "mapped_cos": mapped_cos_data
        })

    materials_data = [
        {
            "id": m.id,
            "subject_id": m.subject_id,
            "topic_id": m.topic_id,
            "filename": m.filename,
            "file_type": m.file_type,
            "chunk_count": m.chunk_count,
            "chromadb_collection": m.chromadb_collection,
            "uploaded_at": str(m.uploaded_at),
        }
        for m in subject.materials
    ]

    return {
        "id": subject.id,
        "name": subject.name,
        "code": subject.code,
        "created_at": str(subject.created_at),
        "units": units_data,
        "materials": materials_data,
        "course_outcomes": cos_data # New field
    }


@router.post("/subjects/", response_model=SubjectResponse)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    subject = Subject(name=data.name, code=data.code)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return SubjectResponse(
        id=subject.id, name=subject.name, code=subject.code, 
        created_at=subject.created_at, unit_count=0, topic_count=0, material_count=0
    )


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # 1. Manually cleanup Materials (files & chromadb)
    # This is critical because they have external side effects (files, vector DB)
    for material in subject.materials:
        if material.file_path and os.path.exists(material.file_path):
            try:
                os.remove(material.file_path)
            except OSError:
                pass # Ignore if file already gone
        # Clean from ChromaDB
        try:
             rag.delete_material_chunks(subject_id, material.id)
        except:
            pass

    # 2. Manually cleanup Generation Jobs (and their questions via cascade)
    # We explicitly query and delete to ensure ORM cascades run if DB FKs fail
    from models import GenerationJob
    jobs = db.query(GenerationJob).filter(GenerationJob.subject_id == subject_id).all()
    for job in jobs:
        db.delete(job)
    
    # 3. Delete Subject (Database Cascade should handle the rest: Units, Topics, COs, LOs)
    db.delete(subject)
    db.commit()
    return {"message": "Subject deleted successfully"}


@router.post("/subjects/{subject_id}/units", response_model=UnitResponse)
def create_unit(subject_id: int, data: UnitCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
        
    unit = Unit(name=data.name, unit_number=data.unit_number, subject_id=subject_id)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return UnitResponse(
        id=unit.id, name=unit.name, unit_number=unit.unit_number,
        subject_id=unit.subject_id, created_at=unit.created_at, topics=[]
    )


@router.delete("/units/{unit_id}")
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    db.delete(unit)
    db.commit()
    return {"message": "Unit deleted"}


@router.post("/units/{unit_id}/topics", response_model=TopicResponse)
def create_topic(unit_id: int, data: TopicCreate, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
        
    topic = Topic(title=data.title, unit_id=unit_id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return TopicResponse(
        id=topic.id, title=topic.title, unit_id=topic.unit_id,
        created_at=topic.created_at, syllabus_data={}
    )


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    db.delete(topic)
    db.commit()
    return {"message": "Topic deleted"}

# ... (Previous code) ...

# --- Materials ---

@router.post("/subjects/{subject_id}/upload-material")
async def upload_material(
    request: Request,
    subject_id: int,
    db: Session = Depends(get_db),
):
    # Manual form parsing to bypass Python 3.14/Pydantic annotation bugs
    form = await request.form()
    
    file = form.get("file")
    unit_id_raw = form.get("unit_id")
    topic_id_raw = form.get("topic_id")

    if not file:
         raise HTTPException(status_code=400, detail="Missing 'file' field in upload data")
    
    # Check if we got an UploadFile or a string error
    filename = getattr(file, "filename", None)
    if not filename:
         # Detect if frontend stringified the object (e.g., "[object Object]")
         if isinstance(file, str) and "[object Object]" in file:
              raise HTTPException(status_code=400, detail="Invalid file format: Detected stringified object from Web frontend.")
         raise HTTPException(status_code=400, detail="No filename found for uploaded file. Ensure you are sending a multipart form.")
    
    topic_id = None
    if topic_id_raw is not None and str(topic_id_raw).strip() != "":
        try:
            topic_id = int(topic_id_raw)
        except (ValueError, TypeError):
            topic_id = None

    unit_id = None
    if unit_id_raw is not None and str(unit_id_raw).strip() != "":
        try:
            unit_id = int(unit_id_raw)
        except (ValueError, TypeError):
            unit_id = None

    # If topic provided but no unit, infer unit
    if topic_id and not unit_id:
        topic_obj = db.query(Topic).filter(Topic.id == topic_id).first()
        if topic_obj:
            unit_id = topic_obj.unit_id

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Determine file type
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx", "txt"):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported")

    # Save file
    timestamp = int(time.time())
    save_name = f"{subject_id}_{timestamp}_{filename}"
    save_path = os.path.join("./uploads", save_name)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # Extract text
    text = rag.extract_text(save_path, ext)

    # Chunk
    chunks = rag.chunk_text(text)

    # Ingest into ChromaDB with metadata (Task 1)
    # Note: rag.ingest now handles string casting internally
    rag.ingest(
        subject_id=subject_id,
        material_id=0, # temp
        chunks=chunks,
        unit_id=unit_id,
        topic_id=topic_id,
        source=filename
    )

    # Save DB record
    material = StudyMaterial(
        subject_id=subject_id,
        unit_id=unit_id,
        topic_id=topic_id,
        filename=filename,
        file_type=ext,
        file_path=save_path,
        content_text=text,
        chunk_count=chunk_count,
        chromadb_collection=f"subject_{subject_id}",
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    # Re-ingest with correct material_id
    rag.delete_material_chunks(subject_id, material.id)
    rag.ingest(
        subject_id=subject_id,
        material_id=material.id,
        chunks=chunks,
        unit_id=unit_id,
        topic_id=topic_id,
        source=filename
    )

    return {
        "id": material.id,
        "filename": material.filename,
        "chunk_count": chunk_count,
        "file_type": ext,
        "topic_id": topic_id,
    }


@router.get("/subjects/{subject_id}/materials", response_model=List[MaterialResponse])
def list_materials(subject_id: int, db: Session = Depends(get_db)):
    materials = db.query(StudyMaterial).filter(StudyMaterial.subject_id == subject_id).all()
    return materials


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(StudyMaterial).filter(StudyMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Clean file
    if material.file_path and os.path.exists(material.file_path):
        try:
            os.remove(material.file_path)
        except OSError:
            pass
            
    # Clean from ChromaDB
    try:
        rag.delete_material_chunks(material.subject_id, material.id)
    except:
        pass
        
    db.delete(material)
    db.commit()
    return {"message": "Material deleted successfully"}


# --- Topic Syllabus & Sample Questions ---
from schemas import TopicUpdateSyllabus, SampleQuestionCreate, SampleQuestionResponse
from models import SampleQuestion

@router.post("/topics/{topic_id}/syllabus")
def update_topic_syllabus(topic_id: int, data: TopicUpdateSyllabus, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    topic.syllabus_data = data.syllabus_data
    flag_modified(topic, "syllabus_data")
    db.commit()
    return {"message": "Syllabus updated", "syllabus_data": topic.syllabus_data}


@router.post("/topics/{topic_id}/sample-questions")
async def upload_sample_questions(
    request: Request,
    topic_id: int,
    db: Session = Depends(get_db),
):
    """Upload a file (PDF, DOCX, CSV, XLSX) containing sample questions."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    form = await request.form()
    file = form.get("file")
    default_type = str(form.get("question_type", "SHORT")).strip() or "SHORT"
    default_difficulty = str(form.get("difficulty", "Medium")).strip() or "Medium"

    if not file:
        raise HTTPException(status_code=400, detail="Missing 'file' field")

    filename = getattr(file, "filename", None)
    if not filename:
        raise HTTPException(status_code=400, detail="No filename found")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx", "csv", "xlsx", "xls"):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, CSV, and Excel files are supported")

    content = await file.read()

    questions_data = []

    if ext == "csv":
        import csv as csv_mod
        import io
        text_data = content.decode("utf-8-sig")
        reader = csv_mod.reader(io.StringIO(text_data))
        for row in reader:
            # Concatenate all non-empty cells in the row
            text = " | ".join(str(cell).strip() for cell in row if str(cell).strip())
            if text and len(text) > 5:
                questions_data.append({
                    "text": text,
                    "question_type": default_type,
                    "difficulty": default_difficulty,
                })

    elif ext in ("xlsx", "xls"):
        import openpyxl
        import io
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            # Concatenate all non-empty cells in the row
            text = " | ".join(str(cell).strip() for cell in row if cell is not None and str(cell).strip())
            if text and len(text) > 5:
                questions_data.append({
                    "text": text,
                    "question_type": default_type,
                    "difficulty": default_difficulty,
                })
        wb.close()

    elif ext in ("pdf", "docx"):
        import tempfile
        tmp_path = os.path.join(tempfile.gettempdir(), f"sq_{int(time.time())}_{filename}")
        try:
            with open(tmp_path, "wb") as f:
                f.write(content)
            from services import rag
            raw_text = rag.extract_text(tmp_path, ext)

            import re
            lines = re.split(r'\n\s*(?:\d+[\.)\]]\s*|Q\d+[\.)\]:\s])', raw_text)
            for line in lines:
                cleaned = line.strip()
                if cleaned and len(cleaned) > 15:
                    questions_data.append({
                        "text": cleaned,
                        "question_type": default_type,
                        "difficulty": default_difficulty,
                    })
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    if not questions_data:
        raise HTTPException(status_code=400, detail="No questions could be extracted from the file. For CSV/Excel, ensure a 'text' column exists.")

    # Save all extracted questions
    created = []
    for qd in questions_data:
        sq = SampleQuestion(
            topic_id=topic_id,
            text=qd["text"],
            question_type=qd["question_type"],
            difficulty=qd["difficulty"],
            source_file=filename,
        )
        db.add(sq)
        created.append(sq)
    db.commit()

    return {"message": f"Extracted {len(created)} questions from '{filename}'", "count": len(created)}


@router.get("/topics/{topic_id}/sample-questions", response_model=list[SampleQuestionResponse])
def list_sample_questions(topic_id: int, db: Session = Depends(get_db)):
    questions = db.query(SampleQuestion).filter(SampleQuestion.topic_id == topic_id).all()
    return questions


@router.delete("/sample-questions/{sq_id}")
def delete_sample_question(sq_id: int, db: Session = Depends(get_db)):
    sq = db.query(SampleQuestion).filter(SampleQuestion.id == sq_id).first()
    if not sq:
        raise HTTPException(status_code=404, detail="Sample Question not found")
    db.delete(sq)
    db.commit()
    return {"message": "Sample Question deleted"}


@router.get("/subjects/{subject_id}/materials", response_model=list[MaterialResponse])
def list_materials(subject_id: int, db: Session = Depends(get_db)):
    materials = (
        db.query(StudyMaterial)
        .filter(StudyMaterial.subject_id == subject_id)
        .all()
    )
    return materials


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(StudyMaterial).filter(StudyMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Delete from ChromaDB
    rag.delete_material_chunks(material.subject_id, material.id)

    # Delete file from disk
    if material.file_path and os.path.exists(material.file_path):
        os.remove(material.file_path)

    db.delete(material)
    db.commit()
    return {"message": "Material deleted"}


@router.get("/subjects/{subject_id}/rag-status")
def rag_status(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    material_count = (
        db.query(StudyMaterial)
        .filter(StudyMaterial.subject_id == subject_id)
        .count()
    )
    stats = rag.get_stats(subject_id)

    return {
        "subject_id": subject_id,
        "material_count": material_count,
        "total_chunks": stats["total_chunks"],
        "collection": stats["collection"],
        "ready": stats["total_chunks"] > 0
    }
