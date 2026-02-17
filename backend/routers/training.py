from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import Skill, Subject, VettedQuestion, CourseOutcome
from schemas import TrainingStatus, SkillResponse
from services.skill_trainer import run_training_pipeline
from datetime import datetime

router = APIRouter()

@router.post("/start/{subject_id}")
def start_training_job(
    subject_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start the training pipeline for a subject.
    Checks prerequisites (approved/rejected questions, study materials).
    """
    # 1. Check prerequisites
    subject = db.query(Subject).get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    approved_count = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "approved"
    ).count()
    
    rejected_count = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "rejected"
    ).count()

    if approved_count < 5:
        raise HTTPException(status_code=400, detail=f"Need at least 5 approved questions (have {approved_count})")
    
    # Relaxed for prototype - originally required 2 rejected
    # if rejected_count < 2:
    #     raise HTTPException(status_code=400, detail=f"Need at least 2 rejected questions (have {rejected_count})")

    # 2. Get or Create Skill
    skill = db.query(Skill).filter(Skill.subject_id == subject_id).first()
    if not skill:
        skill = Skill(subject_id=subject_id, name=f"{subject.code}-skill", version=1)
        db.add(skill)
        db.commit()
        db.refresh(skill)
    else:
        if skill.training_status in ["generating", "evaluating_baseline", "evaluating_skill"]:
            raise HTTPException(status_code=409, detail="Training already in progress")
        
        # Increment version and reset — save previous score for rollback comparison
        skill.previous_trained_score = skill.trained_score or 0.0
        skill.version += 1
        skill.training_status = "generating"
        skill.training_progress = 0
        skill.training_log = ""
        skill.error_message = None
        skill.auto_deactivated = False
        skill.deactivation_reason = None
        db.commit()

    # 3. Launch Background Task
    background_tasks.add_task(run_training_pipeline, subject_id, skill.id)

    return {
        "skill_id": skill.id, 
        "version": skill.version, 
        "status": "generating", 
        "message": "Training started in background"
    }

@router.get("/status/{subject_id}", response_model=TrainingStatus)
def get_training_status(
    subject_id: int,
    db: Session = Depends(get_db)
):
    """
    Poll the status of the training pipeline.
    """
    skill = db.query(Skill).filter(Skill.subject_id == subject_id).first()
    
    # Calculate dataset stats even if no skill yet
    approved = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "approved"
    ).count()
    rejected = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id, 
        VettedQuestion.verdict == "rejected"
    ).count()
    
    ready = approved >= 5 # Relaxed check

    print(f"[DEBUG] Training Status for {subject_id}: Approved={approved}, Rejected={rejected}, Ready={ready}")

    if not skill:
        return TrainingStatus(
            status="untrained",
            ready_for_training=ready,
            dataset_stats={"approved": approved, "rejected": rejected}
        )

    return TrainingStatus(
        skill_id=skill.id,
        version=skill.version,
        status=skill.training_status,
        progress=skill.training_progress,
        baseline_score=skill.baseline_score,
        trained_score=skill.trained_score,
        improvement_pct=skill.improvement_pct,
        training_log=skill.training_log,
        error_message=skill.error_message,
        ready_for_training=ready,
        dataset_stats={"approved": approved, "rejected": rejected},
        is_active=skill.is_active if skill.is_active is not None else True,
        auto_deactivated=skill.auto_deactivated if skill.auto_deactivated is not None else False,
        deactivation_reason=skill.deactivation_reason,
    )

@router.get("/skill/{subject_id}", response_model=SkillResponse)
def get_active_skill(
    subject_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the content of the active skill.
    """
    skill = db.query(Skill).filter(Skill.subject_id == subject_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="No skill found for this subject")
        
    return skill
