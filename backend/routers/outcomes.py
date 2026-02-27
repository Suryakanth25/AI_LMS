from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from database import get_db
from models import Subject, Unit, Topic, CourseOutcome, LearningOutcome, UnitCOMapping
from schemas import (
    COResponse, COCreate, COUpdate,
    LOResponse, LOCreate, LOUpdate,
    UnitCOMappingUpdate, BloomsDistribution, TopicUpdateSyllabus
)

router = APIRouter(prefix="/api", tags=["outcomes"])

# Valid Bloom's Levels
BLOOMS_LEVELS = ["Knowledge", "Comprehension", "Application", "Analysis", "Synthesis", "Evaluation"]

# --- Course Outcomes (Subject Level) ---

@router.get("/subjects/{subject_id}/cos", response_model=List[COResponse])
def list_subject_cos(subject_id: int, db: Session = Depends(get_db)):
    cos = db.query(CourseOutcome).filter(CourseOutcome.subject_id == subject_id).all()
    return cos

@router.post("/subjects/{subject_id}/cos", response_model=COResponse)
def create_subject_co(subject_id: int, data: COCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    for b_level in data.blooms_levels:
        if b_level not in BLOOMS_LEVELS:
            raise HTTPException(status_code=400, detail=f"Invalid Bloom's level: {b_level}. Must be one of {BLOOMS_LEVELS}")

    # Auto-generate code if missing
    if not data.code:
        # Find a unique code by checking sequentially, starting from count + 1
        base_count = db.query(CourseOutcome).filter(CourseOutcome.subject_id == subject_id).count()
        new_num = base_count + 1
        while True:
            candidate = f"CO-{new_num}"
            exists = db.query(CourseOutcome).filter(
                CourseOutcome.subject_id == subject_id, 
                CourseOutcome.code == candidate
            ).first()
            if not exists:
                data.code = candidate
                break
            new_num += 1
    else:
        # Check uniqueness of user-provided code
        exists = db.query(CourseOutcome).filter(
            CourseOutcome.subject_id == subject_id, 
            CourseOutcome.code == data.code
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="CO code already exists for this subject")

    co = CourseOutcome(
        description=data.description,
        code=data.code,
        blooms_levels=data.blooms_levels,
        blooms_level=data.blooms_levels[0] if data.blooms_levels else "Knowledge",
        subject_id=subject_id
    )
    db.add(co)
    db.commit()
    db.refresh(co)
    return co

@router.put("/cos/{co_id}", response_model=COResponse)
def update_co(co_id: int, data: COUpdate, db: Session = Depends(get_db)):
    co = db.query(CourseOutcome).filter(CourseOutcome.id == co_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="CO not found")
    
    if data.code:
         # Check uniqueness if code is changing
        if data.code != co.code:
             exists = db.query(CourseOutcome).filter(
                CourseOutcome.subject_id == co.subject_id, 
                CourseOutcome.code == data.code
            ).first()
             if exists:
                 raise HTTPException(status_code=400, detail="CO code already exists for this subject")
        co.code = data.code
        
    if data.description:
        co.description = data.description

    if data.blooms_levels:
        for b_level in data.blooms_levels:
            if b_level not in BLOOMS_LEVELS:
                raise HTTPException(status_code=400, detail=f"Invalid Bloom's level: {b_level}. Must be one of {BLOOMS_LEVELS}")
        co.blooms_levels = data.blooms_levels
        # Update legacy single level too
        co.blooms_level = data.blooms_levels[0]

    
    db.commit()
    db.refresh(co)
    return co

@router.delete("/cos/{co_id}")
def delete_co(co_id: int, db: Session = Depends(get_db)):
    co = db.query(CourseOutcome).filter(CourseOutcome.id == co_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="CO not found")
    
    db.delete(co)
    db.commit()
    return {"message": "Course outcome deleted"}


# --- Learning Outcomes (Unit Level) ---

@router.get("/units/{unit_id}/los", response_model=List[LOResponse])
def list_unit_los(unit_id: int, db: Session = Depends(get_db)):
    los = db.query(LearningOutcome).filter(LearningOutcome.unit_id == unit_id).all()
    return los

@router.post("/units/{unit_id}/los", response_model=LOResponse)
def create_unit_lo(unit_id: int, data: LOCreate, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    # Auto-generate code if missing
    if not data.code:
        base_count = db.query(LearningOutcome).filter(LearningOutcome.unit_id == unit_id).count()
        new_num = base_count + 1
        while True:
            candidate = f"LO-{unit.unit_number}.{new_num}"
            exists = db.query(LearningOutcome).filter(
                LearningOutcome.unit_id == unit_id,
                LearningOutcome.code == candidate
            ).first()
            if not exists:
                data.code = candidate
                break
            new_num += 1
    else:
        exists = db.query(LearningOutcome).filter(
            LearningOutcome.unit_id == unit_id,
            LearningOutcome.code == data.code
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="LO code already exists for this unit")

    lo = LearningOutcome(
        description=data.description,
        code=data.code,
        unit_id=unit_id
    )
    db.add(lo)
    db.commit()
    db.refresh(lo)
    return lo

@router.put("/los/{lo_id}", response_model=LOResponse)
def update_lo(lo_id: int, data: LOUpdate, db: Session = Depends(get_db)):
    lo = db.query(LearningOutcome).filter(LearningOutcome.id == lo_id).first()
    if not lo:
        raise HTTPException(status_code=404, detail="LO not found")

    if data.code and data.code != lo.code:
        exists = db.query(LearningOutcome).filter(
            LearningOutcome.unit_id == lo.unit_id,
            LearningOutcome.code == data.code
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="LO code already exists for this unit")
        lo.code = data.code
    
    if data.description:
        lo.description = data.description

    db.commit()
    db.refresh(lo)
    return lo

@router.delete("/los/{lo_id}")
def delete_lo(lo_id: int, db: Session = Depends(get_db)):
    lo = db.query(LearningOutcome).filter(LearningOutcome.id == lo_id).first()
    if not lo:
        raise HTTPException(status_code=404, detail="LO not found")
    
    db.delete(lo)
    db.commit()
    return {"message": "Learning outcome deleted"}


# --- Unit ↔ CO Mapping ---

@router.get("/units/{unit_id}/co-mapping", response_model=List[COResponse])
def get_unit_co_mapping(unit_id: int, db: Session = Depends(get_db)):
    # Return full CO objects mapped to this unit
    mappings = db.query(UnitCOMapping).filter(UnitCOMapping.unit_id == unit_id).all()
    co_ids = [m.co_id for m in mappings]
    if not co_ids:
        return []
    cos = db.query(CourseOutcome).filter(CourseOutcome.id.in_(co_ids)).all()
    return cos

@router.put("/units/{unit_id}/co-mapping")
def update_unit_co_mapping(unit_id: int, data: UnitCOMappingUpdate, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    # Verify all COs exist and belong to the same subject as the unit
    # (Though practically we just duplicate check, strict check is better)
    if data.co_ids:
        count = db.query(CourseOutcome).filter(
            CourseOutcome.id.in_(data.co_ids),
            CourseOutcome.subject_id == unit.subject_id
        ).count()
        if count != len(set(data.co_ids)):
             raise HTTPException(status_code=400, detail="One or more COs do not exist or belong to a different subject")

    # Delete existing mappings
    db.query(UnitCOMapping).filter(UnitCOMapping.unit_id == unit_id).delete()
    
    # Insert new mappings
    for co_id in set(data.co_ids):
        mapping = UnitCOMapping(unit_id=unit_id, co_id=co_id)
        db.add(mapping)
    
    db.commit()
    
    return {"message": f"Mapped {len(set(data.co_ids))} course outcomes to unit", "co_ids": data.co_ids}


# --- Bloom's Taxonomy (Topic Level) ---

@router.get("/topics/{topic_id}/blooms")
def get_topic_blooms(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    syllabus = topic.syllabus_data or {}
    dist = syllabus.get("bloom_distribution", None)
    
    # Return default if not set
    if not dist:
        dist = {k: 0 for k in BLOOMS_LEVELS}
        
    return {"bloom_distribution": dist}

@router.put("/topics/{topic_id}/blooms")
def update_topic_blooms(topic_id: int, data: BloomsDistribution, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Validate sum 100
    total = sum([
        data.Knowledge, data.Comprehension, data.Application, 
        data.Analysis, data.Synthesis, data.Evaluation
    ])
    if total != 100:
        raise HTTPException(status_code=400, detail=f"Bloom's distribution must sum to 100. Current sum: {total}")
    
    # Update JSON
    current_data = topic.syllabus_data or {}
    current_data["bloom_distribution"] = data.dict()
    # Force update generic sqlalchemy JSON detection
    topic.syllabus_data = dict(current_data) 
    
    db.commit()
    return {"bloom_distribution": data.dict()}
