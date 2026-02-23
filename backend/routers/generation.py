import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import (
    Rubric, Subject, Unit, Topic, StudyMaterial,
    GenerationJob, GeneratedQuestion, SampleQuestion, Skill,
    LearningOutcome
)
from schemas import RubricCreate, RubricResponse, GenerateRequest, JobStatusResponse, QuestionResponse
from services import rag, swarm, benchmark

router = APIRouter(prefix="/api", tags=["generation"])


# --- Rubrics ---

@router.get("/rubrics/", response_model=list[RubricResponse])
def list_rubrics(db: Session = Depends(get_db)):
    rubrics = db.query(Rubric).all()
    return rubrics


@router.post("/rubrics/", response_model=RubricResponse)
def create_rubric(data: RubricCreate, db: Session = Depends(get_db)):
    # Rubric is now generic, no subject check here
    
    total_marks = (
        (data.mcq_count * data.mcq_marks_each)
        + (data.short_count * data.short_marks_each)
        + (data.essay_count * data.essay_marks_each)
    )

    rubric = Rubric(
        name=data.name,
        exam_type=data.exam_type,
        total_marks=total_marks,
        duration=data.duration,
        mcq_count=data.mcq_count,
        mcq_marks_each=data.mcq_marks_each,
        short_count=data.short_count,
        short_marks_each=data.short_marks_each,
        essay_count=data.essay_count,
        essay_marks_each=data.essay_marks_each,
    )
    db.add(rubric)
    db.commit()
    db.refresh(rubric)

    return rubric


@router.delete("/rubrics/{rubric_id}")
def delete_rubric(rubric_id: int, db: Session = Depends(get_db)):
    rubric = db.query(Rubric).filter(Rubric.id == rubric_id).first()
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    db.delete(rubric)
    db.commit()
    return {"message": "Rubric deleted"}


# --- Generation ---

async def _run_generation(job_id: int, rubric_id: int):
    """Async generation logic — runs all council phases for each question."""
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        rubric = db.query(Rubric).filter(Rubric.id == rubric_id).first()
        subject = db.query(Subject).filter(Subject.id == job.subject_id).first()

        if not job or not rubric or not subject:
            return

        # Get all topics for this subject
        topics = (
            db.query(Topic)
            .join(Unit)
            .filter(Unit.subject_id == subject.id)
            .all()
        )

        if not topics:
            job.status = "failed"
            job.error_message = "Add units and topics first"
            db.commit()
            return

        # Check materials
        material_count = (
            db.query(StudyMaterial)
            .filter(StudyMaterial.subject_id == subject.id)
            .count()
        )
        if material_count == 0:
            job.status = "failed"
            job.error_message = "Upload study materials first"
            db.commit()
            return

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        # Fetch active skill (if any)
        skill = (
            db.query(Skill)
            .filter(Skill.subject_id == subject.id)
            .order_by(Skill.version.desc())
            .first()
        )
        skill_content = skill.skill_content if skill else ""

        # Check Ollama
        ollama_status = await swarm.check_ollama()
        if not ollama_status["available"]:
            job.status = "failed"
            job.error_message = "Ollama is not running. Start Ollama first."
            db.commit()
            return

        available_models = ollama_status["models"]

        # Build question plan: distribute across topics round-robin
        question_plan = []
        difficulties = ["Easy", "Medium", "Hard"]
        used_chunks = set() # Task 4: De-duplication tracking

        def distribute(q_type, count, marks_each):
            for i in range(count):
                topic = topics[i % len(topics)]
                unit = topic.unit
                diff = difficulties[i % len(difficulties)]
                question_plan.append({
                    "type": q_type,
                    "topic": topic.title,
                    "topic_id": topic.id,
                    "unit_id": unit.id,
                    "unit_name": unit.name,
                    "syllabus_data": topic.syllabus_data or {},
                    "marks": marks_each,
                    "difficulty": diff,
                })

        distribute("MCQ", rubric.mcq_count, rubric.mcq_marks_each)
        distribute("Short Notes", rubric.short_count, rubric.short_marks_each)
        distribute("Essay", rubric.essay_count, rubric.essay_marks_each)

        total = len(question_plan)
        job.total_questions_requested = total
        db.commit()

        total_time = 0.0
        total_confidence = 0.0
        generated_count = 0

        for idx, qp in enumerate(question_plan):
            try:
                # Get Sample Questions for this topic
                sample_qs = (
                    db.query(SampleQuestion)
                    .filter(SampleQuestion.topic_id == qp["topic_id"])
                    # Optimize: you might want to filter by ques_type too, but passing all is fine for context
                    .limit(3)
                    .all()
                )
                sample_qs_text = "\n".join([f"- {sq.text} ({sq.difficulty})" for sq in sample_qs])

                # Get Syllabus Data
                syllabus_data = qp["syllabus_data"] if isinstance(qp["syllabus_data"], dict) else {}

                # Task 3: Taxonomy-Driven Query Generation & Content Enrichment
                unit_id = qp["unit_id"]
                los = db.query(LearningOutcome).filter(LearningOutcome.unit_id == unit_id).all()
                
                # Fetch Mapped COs for this unit
                from models import UnitCOMapping
                co_mappings = db.query(UnitCOMapping).filter(UnitCOMapping.unit_id == unit_id).all()
                mapped_cos = {}
                for m in co_mappings:
                    if m.course_outcome:
                        mapped_cos[m.course_outcome.code] = m.course_outcome.description

                # Inject into syllabus_data for Swarm context
                syllabus_data["los"] = {lo.code: lo.description for lo in los}
                syllabus_data["cos"] = mapped_cos
                
                # Build Search Query: Use primary LO or Topic Name
                search_query = qp["topic"]
                if los:
                    # Cycle through LOs or use first one for query diversity
                    search_query = los[idx % len(los)].description or qp["topic"]
                
                # RAG retrieval with scoped metadata (Task 2)
                import time
                rag_start = time.time()
                context_chunks = rag.retrieve(
                    subject_id=subject.id,
                    query=search_query,
                    n_results=15, # Fetch more candidates for MMR + de-duplication
                    unit_id=qp["unit_id"],
                    topic_id=qp["topic_id"],
                    unit_name=qp["unit_name"]
                )
                
                # Task 4: Session De-duplication
                fresh_context_chunks = []
                for chunk in context_chunks:
                    chunk_hash = hash(chunk[:200] + chunk[-200:]) # Simple hash
                    if chunk_hash not in used_chunks:
                        fresh_context_chunks.append(chunk)
                        used_chunks.add(chunk_hash)
                        if len(fresh_context_chunks) >= 10: # Target chunk count
                            break
                
                context_chunks = fresh_context_chunks if fresh_context_chunks else context_chunks[:5]
                
                rag_time = time.time() - rag_start
                rag_context = "\n\n".join(context_chunks) if context_chunks else "No study material context available."
                
                print(f"\n[DEBUG] 🔍 RAG Scoped Retrieval for Topic '{qp['topic']}'")
                print(f"[DEBUG] Query: '{search_query}' | Chunks: {len(context_chunks)}")

                benchmark.record_phase(
                    db, job_id, idx, "rag_retrieval", "chromadb", rag_time, True
                )

                # Generate via Council
                result = await swarm.generate_single_question(
                    question_type=qp["type"],
                    topic=qp["topic"],
                    subject=subject.name,
                    difficulty=qp["difficulty"],
                    rag_context=rag_context,
                    available_models=available_models,
                    syllabus_data=syllabus_data,
                    sample_questions=sample_qs_text,
                    skill_content=skill_content
                )

                # Record phase benchmarks
                for phase_key, phase_name in [
                    ("agent_a", "agent_a"),
                    ("agent_b", "agent_b_review"),
                    ("agent_c", "agent_c"),
                    ("chairman", "chairman"),
                ]:
                    phase_time = result["timings"].get(phase_key, 0)
                    model_used = result["models_used"].get(phase_key, "unknown")
                    phase_success = not result.get(f"{phase_key}_draft", "").startswith("[ERROR]") if phase_key != "chairman" else True
                    benchmark.record_phase(
                        db, job_id, idx, phase_name, model_used, phase_time, phase_success
                    )

                # Extract question text
                q_data = result.get("question")
                question_text = ""
                options = None
                correct_answer = ""

                # Recursive extraction helper
                def find_question_payload(d):
                    if not isinstance(d, dict): return None
                    print(f"[DEBUG] Checking dict keys: {list(d.keys())}") # LOGGING
                    if "question_text" in d: return d
                    if "question" in d and isinstance(d["question"], str): return d # Handle { "question": "...", "options": ... } logic
                    
                    # Known wrappers
                    for k in ["json", "response", "selected_question", "draft", "MCQ", "Short Notes", "Essay", "result", "output"]:
                        if k in d:
                            print(f"[DEBUG] Descending into wrapper '{k}'") # LOGGING
                            res = find_question_payload(d[k])
                            if res: return res
                    # Generic recursion (bfs style preference or just simple dfs)
                    for k, v in d.items():
                        if isinstance(v, dict):
                            print(f"[DEBUG] Descending into generic key '{k}'") # LOGGING
                            res = find_question_payload(v)
                            if res: return res
                    return None

                print(f"\n[DEBUG] Raw Generation Result Type: {type(result)}")
                print(f"[DEBUG] Raw Generation Result: {result}")

                q_payload = None
                if isinstance(q_data, dict):
                     q_payload = find_question_payload(q_data)
                
                if q_payload:
                    print(f"[DEBUG] Found Payload Keys: {list(q_payload.keys())}")
                else:
                    print("[DEBUG] No Payload Found via Recursive Search")

                question_text = ""
                options = None
                correct_answer = ""

                if q_payload:
                    question_text = q_payload.get("question_text") or q_payload.get("question") or ""
                    
                    # Ensure options is a list if present
                    # Try 'options' OR 'choices'
                    opts = q_payload.get("options") or q_payload.get("choices")
                    print(f"[DEBUG] Raw Options Data: {opts} (Type: {type(opts)})")

                    if isinstance(opts, list):
                        options = opts
                    elif isinstance(opts, str):
                        try:
                            import json
                            # Try parsing if it looks like a list
                            if opts.strip().startswith("["):
                                options = json.loads(opts)
                            else:
                                # Handle single string or comma separated? 
                                # For now, just wrap
                                options = [opts]
                        except:
                            options = [opts]
                    
                    correct_answer = str(q_payload.get("correct_answer", ""))
                elif isinstance(q_data, str):
                    question_text = q_data
                else:
                    # Fallback to Agent A draft if everything else fails
                    question_text = result.get("agent_a_draft", "")

                # Final Safety Net: Never save raw JSON as question text
                if not question_text or question_text.strip().startswith("{"):
                    # Try to extract from string if it looks like JSON
                    if isinstance(question_text, str) and "question_text" in question_text:
                        pass # It's a stringified JSON potentially?
                    else:
                        print(f"[ERROR] Final text validation failed. content: {question_text[:50]}...")
                        question_text = "[EXTRACTION FAILED] Could not parse question text."

                # --- Fallback: Extract options from text if missing ---
                if not options and "MCQ" in result.get("question_type", "MCQ"):
                    print("[DEBUG] Options missing for MCQ. Attempting regex extraction from text.")
                    import re
                    # Pattern: A) or A. or (A) ... followed by text, until next pattern or end
                    # This is a naive splitter but often effective for formatted questions
                    regex = r'(?:^|\s)(?:[A-D][\.\)]|\([A-D]\))\s+.*?(?=(?:\s(?:[A-D][\.\)]|\([A-D]\))\s)|$)'
                    # Better aproach: split by newline if it looks like a list?
                    matches = re.findall(r'(?:^|\n)([A-D][\.\)]\s+.*)', question_text)
                    if not matches:
                         # Try inline A) ... B) ...
                         matches = re.findall(r'([A-D][\.\)]\s+[^A-D\n]+)', question_text)
                    
                    if matches:
                        options = [m.strip() for m in matches]
                        print(f"[DEBUG] Extracted options from text: {options}")

                # ------------------------------------------------------


                gen_time = result["timings"].get("total", 0)
                confidence = result.get("confidence_score", 5.0)

                # Save generated question
                gen_q = GeneratedQuestion(
                    job_id=job_id,
                    topic_id=qp["topic_id"],
                    text=question_text,
                    question_type=qp["type"],
                    options=options,
                    correct_answer=correct_answer,
                    marks=qp["marks"],
                    difficulty=qp["difficulty"],
                    confidence_score=confidence,
                    agent_a_draft=result.get("agent_a_draft"),
                    agent_b_review=result.get("agent_b_review"),
                    agent_c_draft=result.get("agent_c_draft"),
                    chairman_output=result.get("chairman_output"),
                    selected_from=result.get("selected_from"),
                    generation_time_seconds=gen_time,
                    rag_context_used=result.get("rag_context_used"),
                    status="pending",
                )
                db.add(gen_q)

                total_time += gen_time
                total_confidence += confidence
                generated_count += 1

                # Update progress
                job.progress = int((generated_count / total) * 100)
                job.total_questions_generated = generated_count
                db.commit()

            except Exception as e:
                benchmark.record_phase(
                    db, job_id, idx, "error", "none", 0, False, str(e)
                )
                continue

        # Finalize job
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.total_questions_generated = generated_count
        job.total_time_seconds = round(total_time, 2)
        job.avg_time_per_question = round(total_time / generated_count, 2) if generated_count > 0 else 0
        job.avg_confidence_score = round(total_confidence / generated_count, 2) if generated_count > 0 else 0
        job.progress = 100
        db.commit()

    except Exception as e:
        try:
            job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _run_generation_sync(job_id: int, rubric_id: int):
    """Sync wrapper for BackgroundTasks."""
    asyncio.run(_run_generation(job_id, rubric_id))


@router.post("/generate/")
def start_generation(
    data: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    rubric = db.query(Rubric).filter(Rubric.id == data.rubric_id).first()
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    subject = db.query(Subject).filter(Subject.id == data.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Check materials availability at start
    material_count = (
        db.query(StudyMaterial)
        .filter(StudyMaterial.subject_id == subject.id)
        .count()
    )
    if material_count == 0:
        raise HTTPException(status_code=400, detail="Subject has no study materials. Upload materials first.")

    total_questions = rubric.mcq_count + rubric.short_count + rubric.essay_count

    job = GenerationJob(
        rubric_id=rubric.id,
        subject_id=subject.id,
        status="pending",
        progress=0,
        total_questions_requested=total_questions,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_generation_sync, job.id, rubric.id)

    return {
        "job_id": job.id,
        "status": "pending",
        "total_questions_requested": total_questions,
        "message": "Generation started",
    }


@router.get("/generate/job/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/generate/job/{job_id}/questions", response_model=list[QuestionResponse])
def get_job_questions(job_id: int, db: Session = Depends(get_db)):
    questions = (
        db.query(GeneratedQuestion)
        .filter(GeneratedQuestion.job_id == job_id)
        .all()
    )
    return questions


@router.get("/generate/ollama-status")
async def ollama_status():
    status = await swarm.check_ollama()
    return status
