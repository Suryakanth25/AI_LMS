from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from database import get_db
from models import GeneratedQuestion, VettedQuestion, CourseOutcome, GenerationJob, Subject, Rubric
from schemas import VettingSubmit, VettedQuestionResponse

router = APIRouter()

@router.get("/batches")
def get_vetting_batches(db: Session = Depends(get_db)):
    """
    Get all generation jobs as vetting batches with progress stats.
    """
    from sqlalchemy.orm import joinedload
    jobs = db.query(GenerationJob).options(
        joinedload(GenerationJob.subject),
        joinedload(GenerationJob.rubric)
    ).filter(
        GenerationJob.status.in_(["completed", "partial"])
    ).order_by(GenerationJob.created_at.desc()).all()

    batches = []
    for job in jobs:
        total = db.query(func.count(GeneratedQuestion.id)).filter(
            GeneratedQuestion.job_id == job.id
        ).scalar() or 0

        vetted = db.query(func.count(GeneratedQuestion.id)).filter(
            GeneratedQuestion.job_id == job.id,
            GeneratedQuestion.status.in_(["approved", "rejected"])
        ).scalar() or 0

        pending = total - vetted
        progress = round((vetted / total) * 100) if total > 0 else 0

        batches.append({
            "job_id": job.id,
            "subject_name": job.subject.name if job.subject else "Unknown",
            "subject_id": job.subject_id,
            "rubric_name": job.rubric.name if job.rubric else "Unknown",
            "rubric_id": job.rubric_id,
            "total_questions": total,
            "vetted_count": vetted,
            "pending_count": pending,
            "progress": progress,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        })

    return batches

@router.get("/queue")
def get_vetting_queue(
    status: str = "pending",
    job_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get questions waiting for review. Optionally filter by job_id (batch).
    """
    from sqlalchemy.orm import joinedload
    query = db.query(GeneratedQuestion).options(joinedload(GeneratedQuestion.job)).filter(
        GeneratedQuestion.status == status
    )
    if job_id is not None:
        query = query.filter(GeneratedQuestion.job_id == job_id)
    
    questions = query.order_by(GeneratedQuestion.created_at.desc()).limit(limit).all()
    return questions

@router.get("/question/{question_id}")
def get_question_detail(question_id: int, db: Session = Depends(get_db)):
    question = db.query(GeneratedQuestion).filter(GeneratedQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

@router.post("/submit")
def submit_vetting(data: VettingSubmit, db: Session = Depends(get_db)):
    """
    Submit a vetting decision (approve/reject/edit).
    """
    # 1. Update the original generated question status
    gen_q = db.query(GeneratedQuestion).filter(GeneratedQuestion.id == data.question_id).first()
    if not gen_q:
        raise HTTPException(status_code=404, detail="Question not found")
    
    if data.action not in ["approved", "rejected", "edited"]:
        raise HTTPException(status_code=400, detail="Action must be 'approved', 'rejected', or 'edited'")

    # Update GeneratedQuestion status
    gen_q.status = data.action
    gen_q.faculty_feedback = data.faculty_feedback
    gen_q.reviewed_at = datetime.utcnow()
    gen_q.reviewed_by = data.reviewed_by
    
    if data.action == "edited" and data.edited_text:
        gen_q.text = data.edited_text
        # If edited, we treat it as approved but with new text
        gen_q.status = "approved" 

    
    # Helper to clean text if it is JSON
    def extract_text(raw_text):
        if not raw_text: return ""
        import json
        try:
            # Try to parse as JSON
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                # Handle nested Chairman format
                if "json" in parsed and isinstance(parsed["json"], dict):
                    parsed = parsed["json"]
                
                # Extract text field
                return parsed.get("question_text") or parsed.get("question") or raw_text
        except:
            pass
        return raw_text

    final_text = data.edited_text if (data.action == "edited" and data.edited_text) else extract_text(gen_q.text)

    # 2. If approved (or edited->approved), save to VettedQuestion table for training
    if gen_q.status == "approved":
        # Check if already vetted
        existing = db.query(VettedQuestion).filter(VettedQuestion.generated_question_id == gen_q.id).first()
        if not existing:
            vetted_q = VettedQuestion(
                subject_id=gen_q.job.subject_id, # Access subject via job
                topic_id=gen_q.topic_id,
                generated_question_id=gen_q.id,
                question_text=final_text,
                question_type=gen_q.question_type,
                options=gen_q.options,
                correct_answer=gen_q.correct_answer,
                marks=gen_q.marks,
                difficulty=data.difficulty or gen_q.difficulty,
                verdict="approved",
                faculty_feedback=data.faculty_feedback,
                co_mappings=data.co_mappings,
                co_mapping_levels=data.co_mapping_levels,
                blooms_level=data.blooms_level,
                confidence_score=gen_q.confidence_score,
                rag_context_used=gen_q.rag_context_used,
                reviewed_by=data.reviewed_by,
                reviewed_at=datetime.utcnow()
            )
            db.add(vetted_q)
    
    # 3. If rejected, we also save it to VettedQuestion
    elif gen_q.status == "rejected":
        existing = db.query(VettedQuestion).filter(VettedQuestion.generated_question_id == gen_q.id).first()
        if not existing:
            vetted_q = VettedQuestion(
                subject_id=gen_q.job.subject_id, # Access subject via job
                topic_id=gen_q.topic_id,
                generated_question_id=gen_q.id,
                question_text=extract_text(gen_q.text), # Store clean text even for rejected
                question_type=gen_q.question_type,
                options=gen_q.options,
                correct_answer=gen_q.correct_answer,
                marks=gen_q.marks,
                difficulty=gen_q.difficulty,
                verdict="rejected",
                faculty_feedback=data.faculty_feedback,
                rejection_reason=data.rejection_reason,
                co_mappings=[], 
                blooms_level=data.blooms_level,
                confidence_score=gen_q.confidence_score,
                rag_context_used=gen_q.rag_context_used,
                reviewed_by=data.reviewed_by,
                reviewed_at=datetime.utcnow()
            )
            db.add(vetted_q)

    db.commit()
    return {"message": "Vetting submitted successfully"}

@router.get("/dataset/{subject_id}/stats")
def get_dataset_stats(subject_id: int, db: Session = Depends(get_db)):
    """
    Get stats on vetting progress for a subject.
    """
    approved_count = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "approved"
    ).count()
    
    rejected_count = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "rejected"
    ).count()
    
    return {
        "subject_id": subject_id,
        "approved": approved_count,
        "rejected": rejected_count,
        "total_vetted": approved_count + rejected_count,
        "ready_for_training": approved_count >= 5
    }
