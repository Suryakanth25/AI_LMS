from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Faculty
from auth_utils import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_faculty
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class FacultyResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True

class FacultyMeResponse(FacultyResponse):
    total_subjects: int
    total_questions_generated: int

@router.post("/register", response_model=FacultyResponse)
def register(user_data: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Faculty).filter(Faculty.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = get_password_hash(user_data.password)
    new_faculty = Faculty(name=user_data.name, email=user_data.email, hashed_password=hashed_pwd)
    db.add(new_faculty)
    db.commit()
    db.refresh(new_faculty)
    return new_faculty

@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Faculty).filter(Faculty.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

from models import Subject, GenerationJob
from sqlalchemy import func

@router.get("/me", response_model=FacultyMeResponse)
def get_me(current_user: Faculty = Depends(get_current_faculty), db: Session = Depends(get_db)):
    total_subjects = db.query(Subject).filter(Subject.faculty_id == current_user.id).count()
    
    # Calculate total questions generated for all subjects owned by this faculty
    generated_q_result = db.query(func.sum(GenerationJob.total_questions_generated))\
        .join(Subject, GenerationJob.subject_id == Subject.id)\
        .filter(Subject.faculty_id == current_user.id).scalar()
        
    total_generated = generated_q_result or 0

    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "total_subjects": total_subjects,
        "total_questions_generated": total_generated
    }
