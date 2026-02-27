import asyncio
import logging
import time
import traceback
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import (
    Rubric, Subject, Unit, Topic, StudyMaterial,
    GenerationJob, GeneratedQuestion, SampleQuestion, Skill,
    LearningOutcome, UnitCOMapping, BenchmarkRecord, VettedQuestion
)
from schemas import RubricCreate, RubricResponse, GenerateRequest, JobStatusResponse, QuestionResponse
from services import rag, swarm, benchmark
from services.rag_retriever import retrieve_context_for_generation
from services.novelty import check_novelty, validate_grounding, register_question, get_chunk_usage_counts
from services.redis_cache import RedisCache

logger = logging.getLogger(__name__)

_redis = RedisCache()

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

    # Cascade: delete dependent generation jobs and their children first
    jobs = db.query(GenerationJob).filter(GenerationJob.rubric_id == rubric_id).all()
    for job in jobs:
        # Get question IDs for this job to clean up vetted records
        q_ids = [q.id for q in db.query(GeneratedQuestion).filter(GeneratedQuestion.job_id == job.id).all()]
        if q_ids:
            db.query(VettedQuestion).filter(VettedQuestion.generated_question_id.in_(q_ids)).delete(synchronize_session=False)
        db.query(BenchmarkRecord).filter(BenchmarkRecord.job_id == job.id).delete()
        db.query(GeneratedQuestion).filter(GeneratedQuestion.job_id == job.id).delete()
        db.delete(job)

    db.delete(rubric)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Cannot delete rubric: {str(e)}")
    return {"message": "Rubric and associated jobs deleted"}



# --- Generation ---

async def _run_generation(job_id: int, rubric_id: int, difficulty: str = "Medium"):
    """Async generation logic — runs all council phases for each question."""
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        rubric = db.query(Rubric).filter(Rubric.id == rubric_id).first()
        subject = db.query(Subject).filter(Subject.id == job.subject_id).first()

        if not job or not rubric or not subject:
            return
            
        if not _redis.acquire_generation_lock(subject.id, job_id):
            job.status = "failed"
            job.error_message = "Another generation is in progress for this subject"
            db.commit()
            return
            
        job_locked = True

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
        # We allow material_count == 0 because it can fallback to Sample Questions

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        # Clear session dedup state for fresh generation
        swarm.clear_session()

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
        # Chunk usage tracking is now handled by services.novelty module

        def distribute(q_type, count, marks_each):
            for i in range(count):
                topic = topics[i % len(topics)]
                unit = topic.unit
                diff = difficulty
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
                
                # Build LO/CO text for query builder
                lo_text = ""
                if los:
                    lo_text = los[idx % len(los)].description or qp["topic"]
                co_text = " ".join([desc for desc in mapped_cos.values() if desc]) if mapped_cos else ""
                
                # Determine bloom level from syllabus data
                bloom_level = ""
                bloom_dist = syllabus_data.get("bloom_distribution", {})
                if bloom_dist:
                    # Pick the bloom level with highest weight
                    bloom_level = max(bloom_dist, key=bloom_dist.get) if bloom_dist else ""

                rag_start = time.time()
                
                # Get chunk usage counts for diversity penalty
                chunk_usage = get_chunk_usage_counts(subject.id, qp["topic_id"])
                
                rag_result = retrieve_context_for_generation(
                    subject_id=subject.id,
                    unit_id=qp["unit_id"],
                    topic_id=qp["topic_id"],
                    topic_name=qp["topic"],
                    unit_name=qp["unit_name"],
                    lo_text=lo_text,
                    co_text=co_text,
                    bloom_level=bloom_level,
                    difficulty=qp["difficulty"],
                    question_type=qp["type"],
                    n_results=6,
                    chunk_usage_counts=chunk_usage,
                )
                
                context_chunks = rag_result["chunks"]
                used_chunk_ids = rag_result["chunk_ids"]
                
                rag_time = time.time() - rag_start
                
                # Build labeled context with section info
                labeled_chunks = []
                for i, (chunk, chunk_id) in enumerate(zip(context_chunks, used_chunk_ids)):
                    # Extract page info from the retrieval result's debug_info or metadata
                    page_info = ""
                    section_info = ""
                    
                    # If rag_result contains metadata
                    chunk_meta = rag_result.get("chunk_metadata", {}).get(chunk_id, {})
                    if chunk_meta:
                        page_start = chunk_meta.get("page_start", "?")
                        page_end = chunk_meta.get("page_end", "?")
                        section = chunk_meta.get("section_heading", "")
                        if page_start == page_end or page_end in ("?", "0", 0):
                            page_info = f"(Page {page_start})"
                        else:
                            page_info = f"(Pages {page_start}-{page_end})"
                        if section:
                            section_info = f" [{section}]"
                    
                    labeled_chunks.append(f"[Source {i+1}] {page_info}{section_info}\n{chunk}")
                
                rag_context = "\n\n---\n\n".join(labeled_chunks) if labeled_chunks else ""
                
                # If no study material context, but sample questions exist, use them as synthetic chunks
                if not rag_context and sample_qs:
                    synthetic_chunks = []
                    for i, sq in enumerate(sample_qs):
                        synthetic_chunks.append(f"[Source {i+1}] (Sample Question Reference)\n{sq.text}")
                    rag_context = "\n\n---\n\n".join(synthetic_chunks)
                elif not rag_context:
                    rag_context = "No study material context available."
                
                logger.info(f"RAG Scoped Retrieval for Topic '{qp['topic']}' — {len(rag_result['debug_info'].get('query_variants', []))} variants, {len(context_chunks)} chunks")


                benchmark.record_phase(
                    db, job_id, idx, "rag_retrieval", "chromadb", rag_time, True
                )

                # Generate via Council (V2: with bloom_level + regeneration loop)
                result = await swarm.generate_single_question(
                    question_type=qp["type"],
                    topic=qp["topic"],
                    subject=subject.name,
                    difficulty=qp["difficulty"],
                    rag_context=rag_context,
                    available_models=available_models,
                    syllabus_data=syllabus_data,
                    sample_questions=sample_qs_text,
                    skill_content=skill_content,
                    bloom_level=bloom_level,
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
                    if "question_text" in d: return d
                    if "question" in d and isinstance(d["question"], str): return d
                    
                    for k in ["json", "response", "selected_question", "draft", "MCQ", "Short Notes", "Essay", "result", "output"]:
                        if k in d:
                            res = find_question_payload(d[k])
                            if res: return res
                    for k, v in d.items():
                        if isinstance(v, dict):
                            res = find_question_payload(v)
                            if res: return res
                    return None

                logger.debug(f"Raw result type: {type(result)}, q_data type: {type(q_data)}")

                q_payload = None
                if isinstance(q_data, dict):
                     q_payload = find_question_payload(q_data)
                
                if not q_payload:
                    logger.warning("No question payload found via recursive search")

                question_text = ""
                options = None
                correct_answer = ""

                if q_payload:
                    question_text = q_payload.get("question_text") or q_payload.get("question") or ""
                    
                    # Ensure options is a list if present
                    # Try 'options' OR 'choices'
                    opts = q_payload.get("options") or q_payload.get("choices")

                    import json as json_mod
                    if isinstance(opts, list):
                        options = opts
                    elif isinstance(opts, str):
                        try:
                            if opts.strip().startswith("["):
                                options = json_mod.loads(opts)
                            else:
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
                    if isinstance(question_text, str) and "question_text" in question_text:
                        pass
                    else:
                        logger.warning(f"Final text validation failed: {question_text[:50] if question_text else 'empty'}")
                        question_text = "[EXTRACTION FAILED] Could not parse question text."

                # --- Fallback: Extract options from text if missing ---
                if not options and "MCQ" in result.get("question_type", "MCQ"):
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
                        logger.debug(f"Extracted options from text: {len(options)} found")

                # --- Safety net: Ensure MCQ always has exactly 4 options ---
                if options is not None and "MCQ" in result.get("question_type", "MCQ"):
                    if len(options) > 4:
                        # Keep correct_answer + first 3 others
                        if correct_answer and correct_answer in options:
                            others = [o for o in options if o != correct_answer][:3]
                            options = others + [correct_answer]
                        else:
                            options = options[:4]
                        logger.warning(f"Trimmed MCQ options to 4")
                    elif 0 < len(options) < 4:
                        placeholders = ["None of the above", "All of the above",
                                        "Not applicable", "Cannot be determined"]
                        while len(options) < 4:
                            added = False
                            for ph in placeholders:
                                if ph not in options and ph != correct_answer:
                                    options.append(ph)
                                    added = True
                                    break
                            if not added:
                                options.append(f"Option {len(options) + 1}")
                            if len(options) >= 4:
                                break
                        if correct_answer and correct_answer not in options:
                            options[-1] = correct_answer
                        logger.warning(f"Padded MCQ options to 4")

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
                db.flush()  # Get gen_q.id for novelty registration

                # ─── Post-Generation: Novelty & Grounding ───
                try:
                    # Check novelty (question dedup)
                    novelty_result = check_novelty(
                        db, subject.id, question_text,
                        topic_id=qp["topic_id"],
                        similarity_threshold=0.95,
                    )
                    if not novelty_result["is_novel"]:
                        print(f"[Novelty] ⚠️ Duplicate detected (sim={novelty_result['max_similarity']:.2f})")
                        gen_q.status = "duplicate"
                    
                    # Validate grounding
                    grounding_result = validate_grounding(
                        subject.id, question_text,
                        topic_id=qp["topic_id"],
                    )
                    if not grounding_result["is_grounded"]:
                        print(f"[Grounding] ⚠️ Poorly grounded (score={grounding_result['grounding_score']:.2f})")
                        if gen_q.status == "pending":
                            gen_q.status = "poorly_grounded"
                    
                    # Register question + chunk usage for future diversity
                    register_question(
                        subject_id=subject.id,
                        topic_id=qp["topic_id"],
                        question_id=gen_q.id,
                        question_text=question_text,
                        chunk_ids=used_chunk_ids,
                    )
                except Exception as novelty_err:
                    print(f"[Novelty] Warning: {novelty_err}")

                total_time += gen_time
                total_confidence += confidence
                generated_count += 1

                # Update progress
                job.progress = int((generated_count / total) * 100)
                job.total_questions_generated = generated_count
                db.commit()

            except Exception as e:
                traceback.print_exc()
                benchmark.record_phase(
                    db, job_id, idx, "error", "none", 0, False, str(e)
                )
                # ALWAYS create a row so the slot isn't lost
                try:
                    error_q = GeneratedQuestion(
                        job_id=job_id,
                        topic_id=qp["topic_id"],
                        text=f"[GENERATION ERROR] {str(e)[:200]}",
                        question_type=qp["type"],
                        marks=qp["marks"],
                        difficulty=qp["difficulty"],
                        confidence_score=0.0,
                        status="error",
                        generation_time_seconds=0,
                    )
                    db.add(error_q)
                    generated_count += 1
                    job.progress = int((generated_count / total) * 100)
                    job.total_questions_generated = generated_count
                    db.commit()
                except Exception:
                    pass


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
        except:
            pass
    finally:
        if 'subject' in locals() and subject:
            _redis.release_generation_lock(subject.id)
        db.close()


def _run_generation_sync(job_id: int, rubric_id: int, difficulty: str = "Medium"):
    """Sync wrapper for BackgroundTasks."""
    asyncio.run(_run_generation(job_id, rubric_id, difficulty))


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

    # We skip strict material_count checks here since the generator can fallback to Sample Questions
    # if no study materials are found.

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

    background_tasks.add_task(_run_generation_sync, job.id, rubric.id, data.difficulty)

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
