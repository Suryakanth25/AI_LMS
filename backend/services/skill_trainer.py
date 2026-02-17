import json
import re
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Skill, Subject, VettedQuestion, CourseOutcome, StudyMaterial, TrainingRun, Topic
from database import SessionLocal
from services.swarm import check_ollama, call_ollama, resolve_model


# ──────────────────────────── Constants ────────────────────────────

BLOOMS_VERBS = {
    "Knowledge":    ["define", "list", "state", "name", "identify", "recall", "recognise"],
    "Comprehension":["explain", "describe", "compare", "differentiate", "summarise", "interpret"],
    "Application":  ["implement", "write", "demonstrate", "apply", "solve", "use", "calculate"],
    "Analysis":     ["analyze", "compare", "distinguish", "examine", "classify", "contrast"],
    "Evaluation":   ["evaluate", "justify", "assess", "critique", "judge", "argue"],
    "Creation":     ["design", "create", "develop", "propose", "construct", "formulate"],
    # Short aliases used in OBE contexts
    "Remember":     ["define", "list", "state", "name", "identify", "recall"],
    "Understand":   ["explain", "describe", "compare", "differentiate", "summarise"],
    "Apply":        ["implement", "write", "demonstrate", "apply", "solve", "use"],
    "Analyze":      ["analyze", "compare", "distinguish", "examine", "classify"],
    "Evaluate":     ["evaluate", "justify", "assess", "critique", "judge"],
    "Create":       ["design", "create", "develop", "propose", "construct"],
    # K-level aliases
    "K1": ["define", "list", "state", "name", "identify"],
    "K2": ["explain", "describe", "compare", "differentiate"],
    "K3": ["implement", "write", "demonstrate", "apply", "solve"],
    "K4": ["analyze", "compare", "distinguish", "examine"],
    "K5": ["evaluate", "justify", "assess", "critique"],
    "K6": ["design", "create", "develop", "propose"],
}


# ──────────────────────────── Helpers ──────────────────────────────

def append_log(db: Session, skill_id: int, message: str):
    skill = db.query(Skill).get(skill_id)
    ist_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    timestamp = ist_time.strftime("%H:%M:%S")
    skill.training_log = (skill.training_log or "") + f"\n[{timestamp}] {message}"
    db.commit()


def simple_similarity(s1: str, s2: str) -> float:
    """Character-level similarity ratio (cheap Jaccard on character bigrams)."""
    if not s1 or not s2:
        return 0.0
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    bigrams1 = set(s1[i:i+2] for i in range(len(s1)-1))
    bigrams2 = set(s2[i:i+2] for i in range(len(s2)-1))
    if not bigrams1 or not bigrams2:
        return 0.0
    intersection = bigrams1 & bigrams2
    union = bigrams1 | bigrams2
    return len(intersection) / len(union)


def safe_parse_json(text: str):
    """Try to extract a JSON object from LLM output."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Find first { ... } block
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        if depth == 0:
            try:
                return json.loads(text[start:i+1])
            except json.JSONDecodeError:
                break
    return None


# ──────────────── Evaluation Criteria (Change 2) ──────────────────

def check_structural_validity(output_json: dict | None, question_type: str) -> int:
    """0 or 1: Does the output parse as valid JSON with correct structure?"""
    if not output_json or not isinstance(output_json, dict):
        return 0
    if "question_text" not in output_json:
        return 0

    qt = question_type.upper()
    if "MCQ" in qt:
        opts = output_json.get("options", [])
        if not isinstance(opts, list) or len(opts) != 4:
            return 0
        if "correct_answer" not in output_json:
            return 0
    elif "SHORT" in qt:
        kp = output_json.get("key_points", [])
        if not isinstance(kp, list) or len(kp) < 3:
            return 0
    elif "ESSAY" in qt:
        es = output_json.get("expected_structure", [])
        if not isinstance(es, list) or len(es) < 1:
            return 0
    return 1


def check_topic_relevance(output_json: dict | None, topic_name: str) -> int:
    """0 or 1: Does the question text contain at least one keyword from the topic?"""
    if not output_json or not topic_name:
        return 0
    q_text = (output_json.get("question_text", "") or "").lower()
    # Split topic name into words and check if any appears in question
    topic_words = [w.lower().strip() for w in re.split(r'[\s,\-/]+', topic_name) if len(w) > 2]
    if not topic_words:
        return 1  # Can't check, give benefit of doubt
    for w in topic_words:
        if w in q_text:
            return 1
    return 0


def check_blooms_alignment(output_json: dict | None, blooms_level: str) -> int:
    """0 or 1: Does the question contain verbs appropriate for the expected Bloom's level?"""
    if not output_json or not blooms_level:
        return 0
    q_text = (output_json.get("question_text", "") or "").lower()
    verbs = BLOOMS_VERBS.get(blooms_level, [])
    if not verbs:
        # Try partial match (e.g., "Application" matches "Apply")
        for key, v_list in BLOOMS_VERBS.items():
            if key.lower().startswith(blooms_level.lower()[:4]):
                verbs = v_list
                break
    if not verbs:
        return 0
    for verb in verbs:
        if verb in q_text:
            return 1
    return 0


def check_non_duplication(output_json: dict | None, approved_texts: list[str]) -> int:
    """0 or 1: Generated question is NOT >90% similar to any approved example."""
    if not output_json:
        return 0
    q_text = output_json.get("question_text", "") or ""
    if not q_text:
        return 0
    for approved in approved_texts:
        if simple_similarity(q_text, approved) > 0.90:
            return 0  # Too similar — deduct
    return 1


# ──────────────── Test Case Builder (Change 2) ────────────────────

def build_test_cases(db: Session, subject_id: int) -> list[dict]:
    approved = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "approved"
    ).order_by(VettedQuestion.reviewed_at.desc()).limit(15).all()

    test_cases = []
    approved_texts = [vq.question_text for vq in approved if vq.question_text]

    for vq in approved:
        # Resolve COs
        co_codes = []
        if vq.co_mappings:
            cos = db.query(CourseOutcome).filter(CourseOutcome.id.in_(vq.co_mappings)).all()
            co_codes = [co.code for co in cos]

        # Get Topic Title
        topic_title = "General"
        if vq.topic_id:
            top = db.query(Topic).get(vq.topic_id)
            if top:
                topic_title = top.title

        test_case = {
            "input": f"Generate a {vq.question_type} question about '{topic_title}' "
                     f"that maps to {', '.join(co_codes)} at {vq.blooms_level or 'Application'} level",
            "topic_name": topic_title,
            "question_type": vq.question_type or "MCQ",
            "blooms_level": vq.blooms_level or "Application",
            "co_codes": co_codes,
            "source_question_text": vq.question_text,
        }
        test_cases.append(test_case)

    # Attach full list of approved texts for non-duplication checks
    for tc in test_cases:
        tc["all_approved_texts"] = approved_texts

    return test_cases


# ──────────── Formatting for SKILL.md Prompt (Change 1) ───────────

def format_approved_examples(db: Session, subject_id: int, max_examples: int = 5) -> str:
    """Top 5 approved examples, complete with options/answers."""
    vqs = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "approved"
    ).order_by(
        VettedQuestion.confidence_score.desc().nullslast(),
        VettedQuestion.reviewed_at.desc()
    ).limit(max_examples).all()

    output = []
    for i, vq in enumerate(vqs):
        co_codes = []
        if vq.co_mappings:
            cos = db.query(CourseOutcome).filter(CourseOutcome.id.in_(vq.co_mappings)).all()
            co_codes = [c.code for c in cos]

        item = f"Example {i+1} [{vq.question_type}] [Bloom's: {vq.blooms_level}] COs: {', '.join(co_codes)}\n"
        item += f"Q: {vq.question_text}\n"
        if vq.options and isinstance(vq.options, list):
            for j, opt in enumerate(vq.options):
                item += f"  {chr(65+j)}) {opt}\n"
        if vq.correct_answer:
            item += f"Correct Answer: {vq.correct_answer}\n"
        if vq.faculty_feedback:
            item += f"Faculty Note: {vq.faculty_feedback}\n"
        output.append(item)

    return "\n".join(output)


def format_rejected_examples(db: Session, subject_id: int, max_examples: int = 3) -> str:
    """Top 3 rejected examples with clearest rejection reasons."""
    vqs = db.query(VettedQuestion).filter(
        VettedQuestion.subject_id == subject_id,
        VettedQuestion.verdict == "rejected",
        VettedQuestion.rejection_reason.isnot(None)
    ).order_by(VettedQuestion.reviewed_at.desc()).limit(max_examples).all()

    output = []
    for i, vq in enumerate(vqs):
        item = f"Rejected {i+1} [{vq.question_type}] — Reason: {vq.rejection_reason}\n"
        item += f"Q: {vq.question_text}\n"
        if vq.faculty_feedback:
            item += f"Faculty Note: {vq.faculty_feedback}\n"
        output.append(item)

    return "\n".join(output)


def format_co_context(db: Session, subject_id: int) -> str:
    cos = db.query(CourseOutcome).filter(CourseOutcome.subject_id == subject_id).all()
    lines = []
    for co in cos:
        # Get matching verbs for all this CO's Bloom's levels
        b_levels = co.blooms_levels if co.blooms_levels else [co.blooms_level]
        all_verbs = []
        for bl in b_levels:
            verbs = BLOOMS_VERBS.get(bl, [])[:3] # 3 verbs per level
            all_verbs.extend(verbs)
        
        verb_str = ", ".join(list(set(all_verbs))) if all_verbs else "N/A"
        level_str = "/".join(b_levels)
        lines.append(f"{co.code}: {co.description} → {level_str} → verbs: {verb_str}")
    return "\n".join(lines)


# ──────────────── SKILL.md Generation (Change 1) ──────────────────

async def generate_skill_content(
    subject_name: str,
    subject_code: str,
    approved_examples: str,
    rejected_examples: str,
    co_context: str,
    study_summary: str,
    model: str,
    available_models: list
) -> tuple[str, float]:

    start_time = datetime.now()

    prompt = f"""You must generate a CONCISE instruction document (UNDER 600 words total) for an AI to generate OBE exam questions for:

SUBJECT: {subject_name} ({subject_code})

INPUT DATA — Course Outcomes:
{co_context}

INPUT DATA — Faculty-Approved Examples:
{approved_examples}

INPUT DATA — Faculty-Rejected Examples:
{rejected_examples}

INPUT DATA — Study Material Summary:
{study_summary}

OUTPUT the document with EXACTLY these 5 sections. Be brief and actionable:

## 1. Subject Scope (3 lines max)
- One sentence: what this subject covers
- Comma-separated list of 4-5 major topics

## 2. CO-Bloom's Reference
List each CO on one line with its Bloom's level and 3-4 action verbs.
Do NOT mix question types here — COs are WHAT to test, not HOW.

## 3. Format Rules (max 3 bullets per type)
- MCQ: exactly 4 options, 1 correct, question under 2 sentences, distractors: one misconception + one related-but-wrong + one opposite
- Short Notes: exactly 3-5 key points, first=definition, last=application
- Essay: 3-part structure (intro/body/conclusion), 300-500 words, reference specific concepts

## 4. Faculty Rules (max 5 bullets total)
Extract 3 DO rules from the best approved examples (one concrete pattern each).
Extract 2 DON'T rules from rejected examples (with the rejection reason).
Each rule = one sentence. Be specific, not vague.

## 5. Gold Examples (exactly 3: one MCQ, one Short Notes, one Essay)
Pick the BEST approved example for each type. Show COMPLETE question with all options/answers.
If an example is incomplete, skip it and write a model example based on the approved patterns.

RULES:
- Stay UNDER 600 words
- Return ONLY the markdown. No JSON. No code fences around the document.
- Be concrete and actionable, not descriptive
"""

    response_text, call_time = await call_ollama(model, prompt)
    elapsed = (datetime.now() - start_time).total_seconds()

    return response_text, elapsed


# ──────────────── Evaluation Engine (Change 2) ────────────────────

async def evaluate_with_skill(
    skill_content: str,
    test_cases: list[dict],
    subject_id: int,
    model: str,
    available_models: list,
    use_skill: bool
) -> dict:

    results = []

    for case in test_cases:
        system_prompt = "You are an expert exam question setter. Follow OBE and academic standards."
        user_prompt = ""

        if use_skill and skill_content:
            user_prompt = f"""GENERATION GUIDELINES (from faculty training):
{skill_content}

---
"""
        user_prompt += f"""{case["input"]}

Output valid JSON only with keys: question_text, options (for MCQ), correct_answer, key_points (for Short Notes), expected_structure (for Essay).
Do NOT wrap in markdown. RAW JSON only."""

        start = datetime.now()
        output, call_time = await call_ollama(model, user_prompt, system=system_prompt)
        elapsed = (datetime.now() - start).total_seconds()

        # Parse the output
        parsed = safe_parse_json(output)

        # Score on 4 criteria
        s_valid = check_structural_validity(parsed, case.get("question_type", "MCQ"))
        s_topic = check_topic_relevance(parsed, case.get("topic_name", ""))
        s_blooms = check_blooms_alignment(parsed, case.get("blooms_level", ""))
        s_nodup = check_non_duplication(parsed, case.get("all_approved_texts", []))

        score = (s_valid + s_topic + s_blooms + s_nodup) / 4.0

        results.append({
            "input": case["input"],
            "output": output[:500],  # Truncate for storage
            "parsed": parsed is not None,
            "scores": {
                "structural_validity": s_valid,
                "topic_relevance": s_topic,
                "blooms_alignment": s_blooms,
                "non_duplication": s_nodup,
            },
            "score": score,
            "time_seconds": elapsed
        })

    total = len(results)
    avg_score = sum(r["score"] for r in results) / total if total > 0 else 0.0

    return {
        "total": total,
        "passed": sum(1 for r in results if r["score"] >= 0.5),
        "failed": sum(1 for r in results if r["score"] < 0.5),
        "success_rate": avg_score,
        "results": results
    }


# ──────────────── Main Pipeline (Changes 1-3) ─────────────────────

async def run_training_pipeline(subject_id: int, skill_id: int):
    db = SessionLocal()
    try:
        skill = db.query(Skill).get(skill_id)
        subject = db.query(Subject).get(subject_id)

        # ═══ Phase 1: Preparation ═══
        skill.training_status = "generating"
        skill.training_progress = 0
        append_log(db, skill_id, "Starting training pipeline...")

        # Check Ollama
        status = await check_ollama()
        if not status["available"]:
            raise Exception("Ollama is not running")

        available_models = status["models"]
        model = "phi3.5"
        actual_model = await resolve_model(model, available_models)
        append_log(db, skill_id, f"Using model: {actual_model}")

        # Build Test Cases
        test_cases = build_test_cases(db, subject_id)
        if len(test_cases) < 3:
            append_log(db, skill_id, "WARNING: Few test cases. Training may be weak.")

        skill.test_cases_json = json.dumps(test_cases, default=str)
        skill.total_test_cases = len(test_cases)
        skill.training_progress = 10
        db.commit()

        # ═══ Phase 2: Generate Skill Document ═══
        append_log(db, skill_id, "Generating skill document (≤600 words)...")

        approved_examples = format_approved_examples(db, subject_id, max_examples=5)
        rejected_examples = format_rejected_examples(db, subject_id, max_examples=3)
        co_context = format_co_context(db, subject_id)

        # Study summary: 2-3 sentences only
        materials = db.query(StudyMaterial).filter(
            StudyMaterial.subject_id == subject_id
        ).limit(3).all()
        summaries = []
        for m in materials:
            if m.content_text:
                # Take first 200 chars as a brief summary
                brief = m.content_text[:200].replace("\n", " ").strip()
                summaries.append(brief)
        study_summary = " ".join(summaries)[:400] if summaries else "No study materials available."

        skill_content, gen_time = await generate_skill_content(
            subject.name, subject.code,
            approved_examples, rejected_examples, co_context,
            study_summary,
            actual_model, available_models
        )

        skill.skill_content = skill_content
        skill.generated_by_model = actual_model
        word_count = len(skill_content.split())
        append_log(db, skill_id, f"Skill generated in {gen_time:.1f}s ({word_count} words)")
        skill.training_progress = 30
        db.commit()

        # ═══ Phase 3: Baseline Evaluation ═══
        skill.training_status = "evaluating_baseline"
        append_log(db, skill_id, "Running baseline evaluation (WITHOUT skill)...")
        db.commit()

        baseline_res = await evaluate_with_skill(
            "", test_cases, subject_id, actual_model, available_models, use_skill=False
        )
        skill.baseline_score = baseline_res["success_rate"]
        append_log(db, skill_id, f"Baseline Score: {skill.baseline_score*100:.0f}%")

        skill.training_progress = 50
        db.commit()

        # ═══ Phase 4: Skill Evaluation ═══
        skill.training_status = "evaluating_skill"
        append_log(db, skill_id, "Running skill evaluation (WITH skill)...")
        db.commit()

        skill_res = await evaluate_with_skill(
            skill_content, test_cases, subject_id, actual_model, available_models, use_skill=True
        )
        skill.trained_score = skill_res["success_rate"]

        if skill.baseline_score > 0:
            skill.improvement_pct = (skill.trained_score - skill.baseline_score) * 100
        else:
            skill.improvement_pct = skill.trained_score * 100

        append_log(db, skill_id, f"Trained Score: {skill.trained_score*100:.0f}%")
        append_log(db, skill_id, f"Improvement: {skill.improvement_pct:+.1f}%")

        skill.training_progress = 80
        db.commit()

        # ═══ Phase 5: Version Rollback Check (Change 3) ═══
        prev_score = skill.previous_trained_score or 0.0
        is_first_version = (skill.version <= 1)

        if is_first_version:
            # First training: activate if trained > baseline
            if skill.trained_score >= skill.baseline_score:
                skill.is_active = True
                skill.auto_deactivated = False
                skill.deactivation_reason = None
                append_log(db, skill_id, "✅ First version trained successfully. Skill activated.")
            else:
                skill.is_active = False
                skill.auto_deactivated = True
                reason = (f"Initial training did not improve over baseline "
                          f"({skill.trained_score*100:.0f}% vs {skill.baseline_score*100:.0f}% baseline).")
                skill.deactivation_reason = reason
                append_log(db, skill_id, f"⚠️ {reason} Skill stored but NOT activated.")
        else:
            # Subsequent versions: compare against previous version's score
            if skill.trained_score >= prev_score:
                skill.is_active = True
                skill.auto_deactivated = False
                skill.deactivation_reason = None
                append_log(db, skill_id,
                    f"✅ V{skill.version} scores {skill.trained_score*100:.0f}% ≥ previous {prev_score*100:.0f}%. Activated.")
            else:
                skill.is_active = False
                skill.auto_deactivated = True
                reason = (f"New version scored lower than current active version "
                          f"({skill.trained_score*100:.0f}% vs {prev_score*100:.0f}%). "
                          f"Previous version remains active. Consider adding more diverse vetted examples.")
                skill.deactivation_reason = reason
                append_log(db, skill_id, f"⚠️ {reason}")

        skill.training_status = "complete"
        skill.training_progress = 100
        db.commit()

    except Exception as e:
        print(f"Training failed: {e}")
        skill = db.query(Skill).get(skill_id)
        if skill:
            skill.training_status = "failed"
            skill.error_message = str(e)
            append_log(db, skill_id, f"❌ Failed: {str(e)}")
            db.commit()
    finally:
        db.close()
