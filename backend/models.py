from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    units = relationship("Unit", back_populates="subject", cascade="all, delete-orphan")
    materials = relationship("StudyMaterial", back_populates="subject", cascade="all, delete-orphan")
    course_outcomes = relationship("CourseOutcome", back_populates="subject", cascade="all, delete-orphan")
    generation_jobs = relationship("GenerationJob", back_populates="subject", cascade="all, delete-orphan")


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    unit_number = Column(Integer)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="units")
    topics = relationship("Topic", back_populates="unit", cascade="all, delete-orphan")
    learning_outcomes = relationship("LearningOutcome", back_populates="unit", cascade="all, delete-orphan")
    co_mappings = relationship("UnitCOMapping", back_populates="unit", cascade="all, delete-orphan")


class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    description = Column(String(500), nullable=True) # Optional
    code = Column(String(50)) # e.g. LO-1.1
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)

    unit = relationship("Unit", back_populates="learning_outcomes")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    unit_id = Column(Integer, ForeignKey("units.id"))
    syllabus_data = Column(JSON, default={})  # Keep for Bloom's distribution
    created_at = Column(DateTime, default=datetime.utcnow)

    unit = relationship("Unit", back_populates="topics")
    materials = relationship("StudyMaterial", back_populates="topic", cascade="all, delete-orphan")
    sample_questions = relationship("SampleQuestion", back_populates="topic", cascade="all, delete-orphan")


class CourseOutcome(Base):
    __tablename__ = "course_outcomes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    description = Column(String(500), nullable=True) # Optional
    code = Column(String(50)) # e.g. CO-1
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE")) # Moving to Subject
    blooms_level = Column(String(50), nullable=False, default="Knowledge")
    blooms_levels = Column(JSON, nullable=False, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="course_outcomes")
    unit_mappings = relationship("UnitCOMapping", back_populates="course_outcome", cascade="all, delete-orphan")


class UnitCOMapping(Base):
    __tablename__ = "unit_co_mapping"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False)
    co_id = Column(Integer, ForeignKey("course_outcomes.id", ondelete="CASCADE"), nullable=False)

    unit = relationship("Unit", back_populates="co_mappings")
    course_outcome = relationship("CourseOutcome", back_populates="unit_mappings")

    __table_args__ = (UniqueConstraint('unit_id', 'co_id', name='_unit_co_uc'),)


class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id")) # Keep for legacy/fallback, but prefer topic_id
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    filename = Column(String(500))
    file_type = Column(String(50))
    file_path = Column(String(500))
    content_text = Column(Text)
    chunk_count = Column(Integer, default=0)
    chromadb_collection = Column(String(200))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject", back_populates="materials")
    unit = relationship("Unit")
    topic = relationship("Topic", back_populates="materials")


class SampleQuestion(Base):
    __tablename__ = "sample_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    text = Column(Text, nullable=False)
    question_type = Column(String(50)) # MCQ, Short, Essay
    difficulty = Column(String(50))    # Easy, Medium, Hard
    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic", back_populates="sample_questions")


class Rubric(Base):
    __tablename__ = "rubrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    exam_type = Column(String(50))
    total_marks = Column(Integer, default=0)
    duration = Column(Integer)
    mcq_count = Column(Integer, default=0)
    mcq_marks_each = Column(Integer, default=0)
    short_count = Column(Integer, default=0)
    short_marks_each = Column(Integer, default=0)
    essay_count = Column(Integer, default=0)
    essay_marks_each = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rubric_id = Column(Integer, ForeignKey("rubrics.id"))
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    status = Column(String(50), default="pending")
    progress = Column(Integer, default=0)
    total_questions_requested = Column(Integer, default=0)
    total_questions_generated = Column(Integer, default=0)
    total_time_seconds = Column(Float, default=0)
    avg_time_per_question = Column(Float, default=0)
    avg_confidence_score = Column(Float, default=0)
    error_message = Column(Text, default=None)
    started_at = Column(DateTime, default=None)
    completed_at = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)

    rubric = relationship("Rubric")
    subject = relationship("Subject", back_populates="generation_jobs")
    generated_questions = relationship("GeneratedQuestion", back_populates="job", cascade="all, delete-orphan")


class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("generation_jobs.id", ondelete="CASCADE"))
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    text = Column(Text)
    question_type = Column(String(50))
    options = Column(JSON, nullable=True)
    correct_answer = Column(String(500))
    marks = Column(Integer)
    difficulty = Column(String(50))
    confidence_score = Column(Float, default=0.0)
    agent_a_draft = Column(Text)
    agent_b_review = Column(Text)
    agent_c_draft = Column(Text)
    chairman_output = Column(Text)
    selected_from = Column(String(50))
    generation_time_seconds = Column(Float, default=0.0)
    rag_context_used = Column(Text)
    status = Column(String(50), default="pending")
    faculty_feedback = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("GenerationJob", back_populates="generated_questions")


class VettedQuestion(Base):
    __tablename__ = "vetted_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    generated_question_id = Column(Integer, ForeignKey("generated_questions.id", ondelete="SET NULL"), nullable=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=False)
    options = Column(JSON, nullable=True)
    correct_answer = Column(String(500), nullable=True)
    marks = Column(Integer, nullable=True)
    difficulty = Column(String(50), nullable=True)
    verdict = Column(String(20), nullable=False)  # "approved" or "rejected"
    faculty_feedback = Column(Text, nullable=True)
    rejection_reason = Column(String(100), nullable=True)
    co_mappings = Column(JSON, nullable=False)  # [1, 3, 5]
    co_mapping_levels = Column(JSON, nullable=True)  # {"1": "high", "3": "moderate"}
    confidence_score = Column(Float, nullable=True)
    selected_from = Column(String(50), nullable=True)
    agent_a_draft = Column(Text, nullable=True)
    agent_b_review = Column(Text, nullable=True)
    agent_c_draft = Column(Text, nullable=True)
    chairman_output = Column(Text, nullable=True)
    rag_context_used = Column(Text, nullable=True)
    generation_time_secs = Column(Float, nullable=True)
    blooms_level = Column(String(50), nullable=True)
    reviewed_by = Column(String(200), nullable=True)
    reviewed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    version = Column(Integer, default=1)
    skill_content = Column(Text, nullable=True)
    baseline_score = Column(Float, default=0.0)
    trained_score = Column(Float, default=0.0)
    improvement_pct = Column(Float, default=0.0)
    test_cases_json = Column(Text, nullable=True)
    total_test_cases = Column(Integer, default=0)
    training_status = Column(String(50), default="idle")
    training_progress = Column(Integer, default=0)
    training_log = Column(Text, default="")
    error_message = Column(Text, nullable=True)
    generated_by_model = Column(String(100), nullable=True)
    approved_used = Column(Integer, default=0)
    rejected_used = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    auto_deactivated = Column(Boolean, default=False)
    deactivation_reason = Column(Text, nullable=True)
    previous_trained_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subject = relationship("Subject")


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    run_type = Column(String(50))  # "baseline" or "with_skill"
    run_number = Column(Integer)
    test_input = Column(Text)
    model_output = Column(Text)
    expected_keywords = Column(JSON)
    keywords_found = Column(JSON)
    passed = Column(Boolean)
    score = Column(Float)
    model_used = Column(String(100))
    time_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class BenchmarkRecord(Base):
    __tablename__ = "benchmark_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("generation_jobs.id"))
    question_index = Column(Integer)
    phase = Column(String(50))
    model_used = Column(String(100))
    time_seconds = Column(Float)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
