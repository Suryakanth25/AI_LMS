from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import GenerationJob, GeneratedQuestion, BenchmarkRecord
from services.benchmark import get_job_benchmarks, get_overall_benchmarks

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


@router.get("/")
def overall_benchmarks(db: Session = Depends(get_db)):
    """Get overall benchmark summary across all jobs."""
    return get_overall_benchmarks(db)


@router.get("/job/{job_id}")
def job_benchmarks(job_id: int, db: Session = Depends(get_db)):
    """Get benchmark details for a specific generation job."""
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return get_job_benchmarks(db, job_id)


@router.get("/export")
def export_benchmarks(db: Session = Depends(get_db)):
    """Export full benchmark data as JSON."""
    jobs = db.query(GenerationJob).all()
    export_data = {
        "overall": get_overall_benchmarks(db),
        "jobs": [],
    }

    for job in jobs:
        job_data = {
            "job_id": job.id,
            "rubric_id": job.rubric_id,
            "subject_id": job.subject_id,
            "status": job.status,
            "total_questions_requested": job.total_questions_requested,
            "total_questions_generated": job.total_questions_generated,
            "total_time_seconds": job.total_time_seconds,
            "avg_time_per_question": job.avg_time_per_question,
            "avg_confidence_score": job.avg_confidence_score,
            "created_at": str(job.created_at),
            "benchmarks": get_job_benchmarks(db, job.id),
            "questions": [],
        }

        questions = (
            db.query(GeneratedQuestion)
            .filter(GeneratedQuestion.job_id == job.id)
            .all()
        )
        for q in questions:
            job_data["questions"].append({
                "id": q.id,
                "text": q.text,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "confidence_score": q.confidence_score,
                "selected_from": q.selected_from,
                "generation_time_seconds": q.generation_time_seconds,
                "status": q.status,
            })

        export_data["jobs"].append(job_data)

    return export_data
