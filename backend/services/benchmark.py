from sqlalchemy.orm import Session
from sqlalchemy import func
from models import BenchmarkRecord, GenerationJob, GeneratedQuestion


def record_phase(
    db: Session,
    job_id: int,
    question_index: int,
    phase: str,
    model_used: str,
    time_seconds: float,
    success: bool,
    error: str = None,
):
    """Record a single benchmark phase."""
    record = BenchmarkRecord(
        job_id=job_id,
        question_index=question_index,
        phase=phase,
        model_used=model_used,
        time_seconds=time_seconds,
        success=success,
        error_message=error,
    )
    db.add(record)
    db.commit()


def get_job_benchmarks(db: Session, job_id: int) -> dict:
    """Get benchmark details for a specific job."""
    records = db.query(BenchmarkRecord).filter(BenchmarkRecord.job_id == job_id).all()

    if not records:
        return {"job_id": job_id, "total_records": 0, "total_time": 0}

    total_time = sum(r.time_seconds for r in records)

    # Per-phase averages
    phase_times = {}
    phase_success = {}
    phase_counts = {}
    models_used = set()

    for r in records:
        models_used.add(r.model_used)
        if r.phase not in phase_times:
            phase_times[r.phase] = []
            phase_success[r.phase] = {"success": 0, "total": 0}
        phase_times[r.phase].append(r.time_seconds)
        phase_success[r.phase]["total"] += 1
        if r.success:
            phase_success[r.phase]["success"] += 1

    phase_avg_times = {
        phase: sum(times) / len(times) for phase, times in phase_times.items()
    }
    phase_success_rates = {
        phase: data["success"] / data["total"] if data["total"] > 0 else 0
        for phase, data in phase_success.items()
    }

    return {
        "job_id": job_id,
        "total_records": len(records),
        "total_time": round(total_time, 2),
        "phase_avg_times": {k: round(v, 2) for k, v in phase_avg_times.items()},
        "phase_success_rates": {k: round(v, 3) for k, v in phase_success_rates.items()},
        "models_used": list(models_used),
    }


def get_overall_benchmarks(db: Session) -> dict:
    """Aggregate benchmarks across all jobs.

    Returns a structure the frontend benchmarks page expects:
      - overall_stats: summary numbers
      - phase_timings: avg seconds per council phase
      - council_effectiveness: agent selection counts + vetting status counts
      - question_type_stats: per-type breakdown
    """
    jobs = db.query(GenerationJob).filter(GenerationJob.status == "completed").all()
    questions = db.query(GeneratedQuestion).all()

    total_jobs = len(jobs)
    total_questions = len(questions)

    if total_questions == 0:
        return {
            "overall_stats": {
                "total_jobs": total_jobs,
                "total_questions": 0,
                "avg_confidence": 0,
                "avg_time_per_question": 0,
                "total_time": 0,
                "fastest_question": 0,
                "slowest_question": 0,
            },
            "phase_timings": {},
            "council_effectiveness": {
                "agent_a_selected": 0,
                "agent_c_selected": 0,
                "combined_selected": 0,
                "approved": 0,
                "rejected": 0,
                "pending": 0,
            },
            "question_type_stats": [],
        }

    # Timing stats
    gen_times = [q.generation_time_seconds for q in questions if q.generation_time_seconds]
    avg_time = sum(gen_times) / len(gen_times) if gen_times else 0
    total_time = sum(gen_times) if gen_times else 0
    fastest = min(gen_times) if gen_times else 0
    slowest = max(gen_times) if gen_times else 0

    # Confidence stats
    confidences = [q.confidence_score for q in questions if q.confidence_score is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Council effectiveness — absolute counts
    agent_a_count = sum(1 for q in questions if q.selected_from and "agent a" in q.selected_from.lower())
    agent_c_count = sum(1 for q in questions if q.selected_from and "agent c" in q.selected_from.lower())
    combined_count = sum(1 for q in questions if q.selected_from and "combined" in q.selected_from.lower())

    # Vetting status counts
    approved_count = sum(1 for q in questions if q.status == "approved")
    rejected_count = sum(1 for q in questions if q.status == "rejected")
    pending_count = sum(1 for q in questions if q.status == "pending")

    # Phase benchmarks from BenchmarkRecords
    all_records = db.query(BenchmarkRecord).all()
    phase_times = {}
    for r in all_records:
        if r.phase not in phase_times:
            phase_times[r.phase] = []
        phase_times[r.phase].append(r.time_seconds)

    # Map backend phase names to frontend-friendly keys
    phase_map = {
        "agent_a": "avg_phase_1",
        "agent_b_review": "avg_phase_2",
        "agent_c": "avg_phase_3",
        "chairman": "avg_phase_4",
        "rag_retrieval": "avg_rag_retrieval",
    }
    phase_timings = {}
    for phase, times in phase_times.items():
        key = phase_map.get(phase, f"avg_{phase}")
        phase_timings[key] = round(sum(times) / len(times), 2)

    # Question type stats
    type_groups: dict = {}
    for q in questions:
        qt = q.question_type or "Unknown"
        if qt not in type_groups:
            type_groups[qt] = {"count": 0, "times": [], "confidences": []}
        type_groups[qt]["count"] += 1
        if q.generation_time_seconds:
            type_groups[qt]["times"].append(q.generation_time_seconds)
        if q.confidence_score is not None:
            type_groups[qt]["confidences"].append(q.confidence_score)

    question_type_stats = []
    for qt, g in type_groups.items():
        question_type_stats.append({
            "type": qt,
            "count": g["count"],
            "avg_time": round(sum(g["times"]) / len(g["times"]), 2) if g["times"] else 0,
            "avg_confidence": round(sum(g["confidences"]) / len(g["confidences"]), 2) if g["confidences"] else 0,
        })

    return {
        "overall_stats": {
            "total_jobs": total_jobs,
            "total_questions": total_questions,
            "avg_confidence": round(avg_confidence, 2),
            "avg_time_per_question": round(avg_time, 2),
            "total_time": round(total_time, 2),
            "fastest_question": round(fastest, 2),
            "slowest_question": round(slowest, 2),
        },
        "phase_timings": phase_timings,
        "council_effectiveness": {
            "agent_a_selected": agent_a_count,
            "agent_c_selected": agent_c_count,
            "combined_selected": combined_count,
            "approved": approved_count,
            "rejected": rejected_count,
            "pending": pending_count,
        },
        "question_type_stats": question_type_stats,
    }
