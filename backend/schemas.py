from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


# --- Subject ---
class SubjectCreate(BaseModel):
    name: str
    code: str

class SubjectResponse(BaseModel):
    id: int
    name: str
    code: str
    created_at: datetime
    unit_count: int = 0
    topic_count: int = 0
    material_count: int = 0

    class Config:
        from_attributes = True

# --- Course Outcome ---
class COCreate(BaseModel):
    description: Optional[str] = None
    code: Optional[str] = None
    blooms_levels: List[str] # ["Knowledge", "Comprehension"]

class COUpdate(BaseModel):
    description: Optional[str] = None
    code: Optional[str] = None
    blooms_levels: Optional[List[str]] = None

class COResponse(BaseModel):
    id: int
    description: Optional[str] = None
    code: str
    subject_id: int
    blooms_levels: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

# --- Learning Outcome ---
class LOCreate(BaseModel):
    description: Optional[str] = None
    code: Optional[str] = None

class LOUpdate(BaseModel):
    description: Optional[str] = None
    code: Optional[str] = None

class LOResponse(BaseModel):
    id: int
    description: Optional[str] = None
    code: str
    unit_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class UnitCOMappingUpdate(BaseModel):
    co_ids: List[int]

# --- Unit ---
class UnitCreate(BaseModel):
    name: str
    unit_number: int

class UnitResponse(BaseModel):
    id: int
    name: str
    unit_number: int
    subject_id: int
    created_at: datetime
    learning_outcomes: List[LOResponse] = []
    mapped_cos: List[COResponse] = []

    class Config:
        from_attributes = True


# --- Topic ---
class TopicCreate(BaseModel):
    title: str

class BloomsDistribution(BaseModel):
    Knowledge: int = 0
    Comprehension: int = 0
    Application: int = 0
    Analysis: int = 0
    Synthesis: int = 0
    Evaluation: int = 0

class TopicUpdateSyllabus(BaseModel):
    syllabus_data: dict

class TopicResponse(BaseModel):
    id: int
    title: str
    unit_id: int
    created_at: datetime
    syllabus_data: dict = {}
    bloom_distribution: Optional[dict] = None

    class Config:
        from_attributes = True

# --- Subject Detail ---
class SubjectDetail(BaseModel):
    id: int
    name: str
    code: str
    created_at: datetime
    units: List[UnitResponse] = [] # Nested UnitResponse now has LOs and Mapped COs
    materials: list = []
    course_outcomes: List[COResponse] = [] # Subject-level COs

    class Config:
        from_attributes = True


# --- Study Material ---
class MaterialResponse(BaseModel):
    id: int
    subject_id: int
    unit_id: Optional[int] = None
    topic_id: Optional[int] = None
    filename: str
    file_type: str
    chunk_count: int
    chromadb_collection: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


# --- Sample Question ---
class SampleQuestionCreate(BaseModel):
    text: str
    question_type: str
    difficulty: str

class SampleQuestionResponse(BaseModel):
    id: int
    topic_id: int
    text: str
    question_type: str
    difficulty: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Rubric ---
class RubricCreate(BaseModel):
    name: str
    exam_type: str
    duration: int
    mcq_count: int = 0
    mcq_marks_each: int = 0
    short_count: int = 0
    short_marks_each: int = 0
    essay_count: int = 0
    essay_marks_each: int = 0

class RubricResponse(BaseModel):
    id: int
    name: str
    exam_type: str
    total_marks: int
    duration: int
    mcq_count: int
    mcq_marks_each: int
    short_count: int
    short_marks_each: int
    essay_count: int
    essay_marks_each: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- Generation ---
class GenerateRequest(BaseModel):
    rubric_id: int
    subject_id: int

class JobStatusResponse(BaseModel):
    id: int
    rubric_id: int
    subject_id: int
    status: str
    progress: int
    total_questions_requested: int
    total_questions_generated: int
    total_time_seconds: float
    avg_time_per_question: float
    avg_confidence_score: float
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class JobSummary(BaseModel):
    id: int
    subject_id: int
    rubric_id: int

    class Config:
        from_attributes = True

class QuestionResponse(BaseModel):
    id: int
    job_id: int
    topic_id: Optional[int] = None
    text: Optional[str] = None
    question_type: str
    options: Optional[list] = None
    correct_answer: Optional[str] = None
    marks: int
    difficulty: Optional[str] = None
    confidence_score: float
    agent_a_draft: Optional[str] = None
    agent_b_review: Optional[str] = None
    agent_c_draft: Optional[str] = None
    chairman_output: Optional[str] = None
    selected_from: Optional[str] = None
    generation_time_seconds: float
    rag_context_used: Optional[str] = None
    status: str
    faculty_feedback: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    
    job: Optional[JobSummary] = None

    class Config:
        from_attributes = True


# --- Vetting & Training ---


class VettingSubmit(BaseModel):
    question_id: int
    action: str  # "approved", "rejected", "edited"
    co_mappings: List[int] = []
    co_mapping_levels: Dict[str, str] = {}
    blooms_level: Optional[str] = None
    faculty_feedback: Optional[str] = None
    rejection_reason: Optional[str] = None
    edited_text: Optional[str] = None
    difficulty: Optional[str] = None
    reviewed_by: str = "Faculty"

class VettedQuestionResponse(BaseModel):
    id: int
    question_text: str
    question_type: str
    verdict: str
    faculty_feedback: Optional[str] = None
    co_mappings: List[int] = []
    blooms_level: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TrainingStatus(BaseModel):
    skill_id: Optional[int] = None
    version: int = 0
    status: str
    progress: int = 0
    baseline_score: float = 0.0
    trained_score: float = 0.0
    improvement_pct: float = 0.0
    training_log: str = ""
    error_message: Optional[str] = None
    approved_used: int = 0
    rejected_used: int = 0
    total_test_cases: int = 0
    generated_by_model: Optional[str] = None
    ready_for_training: bool = False
    dataset_stats: dict = {}
    is_active: bool = True
    auto_deactivated: bool = False
    deactivation_reason: Optional[str] = None

class SkillResponse(BaseModel):
    id: int
    subject_id: int
    version: int
    skill_content: Optional[str] = None
    trained_score: float
    is_active: bool = True
    auto_deactivated: bool = False
    deactivation_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


