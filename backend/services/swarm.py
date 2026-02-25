import httpx
import json
import time
import re
import hashlib
import asyncio
from difflib import SequenceMatcher

OLLAMA_BASE = "http://localhost:11434"

AGENTS = {
    "logician": {
        "model": "phi3.5",
        "role": "Strict adherence to facts from the study material. Generate questions grounded in source content.",
        "temperature": 0.5,  # Lower = more precise/factual
    },
    "creative": {
        "model": "gemma2:2b",
        "role": "Review questions for accuracy, clarity, and suggest improvements while staying true to source material.",
        "temperature": 0.7,
    },
    "technician": {
        "model": "qwen2.5:3b",
        "role": "Generate precise, well-structured questions with proper formatting and technical accuracy.",
        "temperature": 0.5,  # Lower = more precise
    },
    "chairman": {
        "model": "phi3.5",
        "role": "Final arbiter. Score drafts, select the best, assign confidence score based on factual accuracy.",
        "temperature": 0.4,  # Lowest = most deterministic selection
    },
}

# ─── Tuning Knobs ───
MAX_ATTEMPTS = 3
MIN_USED_CHUNKS_BY_BLOOM = {
    "remember": 1, "understand": 1,
    "apply": 2, "analyze": 2, "evaluate": 2, "create": 2,
    "knowledge": 1, "comprehension": 1, "application": 2,
    "analysis": 2, "synthesis": 2, "evaluation": 2,
}
DIRECTNESS_PREFIX_BLACKLIST = [
    "what is", "define", "state the", "list the", "name the",
    "mention the", "what are", "give the definition",
]
FORBIDDEN_SCENARIO_PATTERNS = [
    r"\ba clinician\b", r"\ba patient named\b", r"\bdr\.\s+\w+\b",
]
DEDUP_SIMILARITY_THRESHOLD = 0.85

# Session-level dedup state (reset per generation job)
_session_questions: list[str] = []


# ─── Core Ollama Interface (unchanged) ───

async def check_ollama() -> dict:
    """Check if Ollama is available and list loaded models."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"available": True, "models": models}
    except Exception:
        pass
    return {"available": False, "models": []}


async def resolve_model(preferred: str, available: list) -> str:
    """Resolve the best available model match."""
    if preferred in available:
        return preferred
    for m in available:
        if m.startswith(preferred) or preferred.startswith(m.split(":")[0]):
            return m
    if available:
        return available[0]
    return preferred


async def call_ollama(model: str, prompt: str, system: str = "", temperature: float = 0.7, num_predict: int = 1024) -> tuple[str, float]:
    """Call Ollama /api/generate and return (response_text, elapsed_seconds)."""
    start = time.time()
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)

            elapsed = time.time() - start
            if resp.status_code == 200:
                data = resp.json()
                return (data.get("response", ""), elapsed)
            else:
                return (f"[ERROR] HTTP {resp.status_code}: {resp.text}", elapsed)
    except Exception as e:
        elapsed = time.time() - start
        return (f"[ERROR] {str(e)}", elapsed)


def parse_json(text: str):
    """Attempt to parse JSON from LLM output, handling markdown fences and extra text."""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        depth = 0
        for i in range(start_idx, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start_idx : i + 1])
                except json.JSONDecodeError:
                    break
    return None


def extract_skill_sections(skill_content: str) -> str:
    """Extract only Sections 2-4 from a SKILL.md document for prompt injection."""
    if not skill_content:
        return ""
    
    lines = skill_content.split("\n")
    include = False
    result = []
    
    for line in lines:
        stripped = line.strip().lower()
        if "## 2" in stripped or "co-bloom" in stripped or "co to bloom" in stripped or "co reference" in stripped:
            include = True
        if "## 5" in stripped or "gold example" in stripped:
            include = False
            break
        if include:
            result.append(line)
    
    extracted = "\n".join(result).strip()
    if len(extracted) < 50:
        return skill_content[:1500]
    return extracted


# ─── (2) RAG Context Formatting: Labeled Chunks ───

def format_rag_as_labeled_chunks(rag_context: str) -> tuple[str, dict[str, str]]:
    """
    Convert raw RAG context into labeled chunks [C1], [C2], ...
    Returns: (formatted_string, chunk_map: {chunk_id: chunk_text})
    """
    if not rag_context or rag_context.strip() == "No study material context available.":
        return rag_context, {}

    # Split by double newline (chunks were joined this way in generation.py)
    raw_chunks = [c.strip() for c in rag_context.split("\n\n") if c.strip()]
    
    if not raw_chunks:
        return rag_context, {}

    chunk_map = {}
    labeled_parts = []
    for i, chunk in enumerate(raw_chunks):
        chunk_id = f"C{i + 1}"
        chunk_map[chunk_id] = chunk
        labeled_parts.append(f"[{chunk_id}] {chunk}")
    
    return "\n\n".join(labeled_parts), chunk_map


# ─── (3B) Bloom Resolution ───

BLOOM_LEVELS_ORDERED = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
BLOOM_ALIASES = {
    "knowledge": "remember", "comprehension": "understand",
    "application": "apply", "analysis": "analyze",
    "synthesis": "create", "evaluation": "evaluate",
}

def resolve_bloom(bloom_level: str = "", syllabus_data: dict = None, difficulty: str = "Medium") -> str:
    """Resolve bloom level from explicit input, syllabus, or difficulty-based default."""
    if bloom_level:
        bl = bloom_level.lower().strip()
        bl = BLOOM_ALIASES.get(bl, bl)
        if bl in BLOOM_LEVELS_ORDERED:
            return bl
    
    # Try syllabus bloom_distribution
    if syllabus_data and syllabus_data.get("bloom_distribution"):
        dist = syllabus_data["bloom_distribution"]
        if dist:
            top = max(dist, key=dist.get).lower().strip()
            top = BLOOM_ALIASES.get(top, top)
            if top in BLOOM_LEVELS_ORDERED:
                return top
    
    # Default based on difficulty
    defaults = {"easy": "understand", "medium": "apply", "hard": "analyze"}
    return defaults.get(difficulty.lower(), "apply")


def is_higher_order_bloom(bloom: str) -> bool:
    """Check if bloom level requires multi-step reasoning."""
    return bloom in ("apply", "analyze", "evaluate", "create")


# ─── (3A) Bloom-Aware Verb Bank ───

BLOOM_VERB_BANK = {
    "remember": "recall, identify, list, define, recognize",
    "understand": "explain, summarize, classify, compare, interpret",
    "apply": "apply, demonstrate, solve, implement, calculate, use in a scenario",
    "analyze": "analyze, differentiate, compare and contrast, examine, investigate, deconstruct",
    "evaluate": "evaluate, justify, critique, judge, argue, recommend, prioritize",
    "create": "design, construct, propose, formulate, synthesize, develop a plan",
}


# ─── (3C) Validation Gate ───

def validate_question_output(
    parsed: dict,
    question_type: str,
    bloom: str,
    difficulty: str,
    chunk_map: dict,
) -> list[str]:
    """
    Validate a generated question JSON against grounding and standardness rules.
    Returns list of error strings (empty = valid).
    """
    errors = []
    if not parsed or not isinstance(parsed, dict):
        errors.append("Output is not a valid JSON object")
        return errors

    # Schema: required keys
    qt = parsed.get("question_text") or parsed.get("question")
    if not qt or not isinstance(qt, str) or len(qt.strip()) < 10:
        errors.append("Missing or empty question_text")

    # MCQ-specific
    if question_type == "MCQ":
        opts = parsed.get("options", [])
        if not isinstance(opts, list) or len(opts) < 4:
            errors.append(f"MCQ must have 4 options, got {len(opts) if isinstance(opts, list) else 0}")
        ca = parsed.get("correct_answer", "")
        if isinstance(ca, str) and ca.strip() and ca.strip()[0] not in "ABCD":
            errors.append(f"correct_answer should start with A/B/C/D, got '{ca[:10]}'")

    # Citation check
    used_chunks = parsed.get("used_chunks", [])
    min_chunks = MIN_USED_CHUNKS_BY_BLOOM.get(bloom, 1)
    if is_higher_order_bloom(bloom) or difficulty.lower() in ("medium", "hard"):
        if len(used_chunks) < min_chunks:
            errors.append(f"Bloom '{bloom}' requires >={min_chunks} used_chunks, got {len(used_chunks)}")

    # Quote validity (lightweight)
    quotes = parsed.get("supporting_quotes", [])
    if chunk_map and quotes:
        for sq in quotes[:3]:  # Check first 3 only for speed
            cid = sq.get("chunk_id", "")
            quote = sq.get("quote", "")
            if cid in chunk_map and quote:
                # Check if quote appears as substring (case-insensitive, fuzzy)
                if quote.lower()[:50] not in chunk_map[cid].lower():
                    errors.append(f"Quote from {cid} not found in chunk text")

    # Directness check (Bloom-aware)
    if qt and (is_higher_order_bloom(bloom) or difficulty.lower() in ("medium", "hard")):
        qt_lower = qt.lower().strip()
        for prefix in DIRECTNESS_PREFIX_BLACKLIST:
            if qt_lower.startswith(prefix):
                errors.append(f"Question starts with '{prefix}' — too direct for Bloom '{bloom}'")
                break

    return errors


# ─── (5) Dedup ───

def _normalize_text(text: str) -> str:
    """Normalize question text for dedup comparison."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def is_duplicate(question_text: str) -> bool:
    """Check if question is too similar to any previous question in this session."""
    normalized = _normalize_text(question_text)
    for prev in _session_questions:
        ratio = SequenceMatcher(None, normalized, prev).ratio()
        if ratio >= DEDUP_SIMILARITY_THRESHOLD:
            return True
    return False


def register_in_session(question_text: str):
    """Register a question in the session dedup list."""
    _session_questions.append(_normalize_text(question_text))


def clear_session():
    """Clear session dedup state (call at start of each generation job)."""
    _session_questions.clear()


# ─── Format Instructions (per question type, with citation fields) ───

def get_format_instruction(question_type: str, bloom: str) -> str:
    """Build format instruction JSON schema with citation fields."""
    citation_fields = '"used_chunks": ["C1", "C3"], "supporting_quotes": [{"chunk_id": "C1", "quote": "exact text from chunk"}]'
    
    if question_type == "MCQ":
        return f"""Output JSON format (RAW JSON ONLY, no markdown):
{{"question_text": "...", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "correct_answer": "B", "explanation": "Why B is correct, referencing study material...", {citation_fields}}}"""
    elif question_type == "Short Notes":
        return f"""Output JSON format (RAW JSON ONLY, no markdown):
{{"question_text": "...", "key_points": ["Point 1", "Point 2", "Point 3"], "marks": 5, {citation_fields}}}"""
    elif question_type == "Essay":
        return f"""Output JSON format (RAW JSON ONLY, no markdown):
{{"question_text": "...", "expected_structure": ["Intro...", "Body...", "Conclusion..."], "marks": 10, "word_limit": 500, {citation_fields}}}"""
    return ""


# ─── Prompt Builders (per agent) ───

def build_agent_a_prompt(
    subject, topic, question_type, difficulty, bloom, material_section,
    syllabus_context, sample_context, skill_context, format_instruction,
    attempt: int = 1, diversity_hint: str = "",
) -> str:
    """Build Agent A (Logician) prompt with Bloom-aware instructions."""
    bloom_verbs = BLOOM_VERB_BANK.get(bloom, BLOOM_VERB_BANK["apply"])
    
    bloom_instruction = ""
    if is_higher_order_bloom(bloom):
        bloom_instruction = f"""
BLOOM'S LEVEL: {bloom.upper()} — You MUST use verbs like: {bloom_verbs}.
- Do NOT write simple recall/definition questions.
- The question MUST require multi-step reasoning, comparison, application, or synthesis.
- Use information from 2+ different chunks [C1], [C2], etc. to create a question that COMBINES concepts.
- For MCQs: distractors must be plausible alternatives that test understanding, not trivially wrong."""
    else:
        bloom_instruction = f"""
BLOOM'S LEVEL: {bloom.upper()} — Use verbs like: {bloom_verbs}.
- Direct recall questions are acceptable at this level."""
    
    diversity_section = ""
    if attempt == 2:
        diversity_section = """
DIVERSITY REQUIREMENT (Attempt 2):
- Focus on: applications, edge cases, limitations, comparisons, or clinical implications.
- Do NOT repeat the same angle as a typical textbook question.
- Combine information from 2+ labeled chunks."""
    elif attempt >= 3:
        diversity_section = """
SYNTHESIS REQUIREMENT (Final attempt):
- You MUST create a multi-concept synthesis question.
- Use patterns like: compare/contrast, cause-and-effect, best-method-with-justification, or clinical decision-making.
- The question MUST draw from at least 2 different chunks.
- Avoid any format that can be answered by quoting a single sentence."""

    return f"""You are an expert question paper setter for {subject}.

{material_section}

{syllabus_context}
{sample_context}
{skill_context}

Generate exactly 1 {question_type} question about "{topic}".
Difficulty: {difficulty}
{bloom_instruction}
{diversity_section}
{diversity_hint}

GROUNDING & CITATION RULES:
- Question MUST be derived from the STUDY MATERIAL chunks above.
- You MUST cite which chunks you used in "used_chunks" (e.g., ["C1", "C3"]).
- You MUST include "supporting_quotes" with exact quotes from those chunks.
- Do NOT hallucinate facts not in the material.

EXAM STYLE RULES:
- STANDALONE: Do NOT write "based on the passage" or "according to the document". Write it as a standard exam question.
- VARIETY: Cover different aspects — use cases, limitations, comparisons, implementation details.
- Do NOT start with "What is", "Define", "State", "List", or "Name" unless Bloom level is Remember/Understand.
- Explicitly map to a Learning Outcome or Course Outcome from the syllabus if available.

OUTPUT: RAW JSON ONLY. No markdown, no wrapping, no comments.
CRITICAL: "question_text" must be a plain text string at the top level.

{format_instruction}"""


def build_agent_b_prompt(
    question_type, topic, rag_labeled, syllabus_context, agent_a_output, bloom,
) -> str:
    """Build Agent B (Creative Reviewer) prompt with structured review schema."""
    return f"""Review this {question_type} question about "{topic}" at Bloom's level: {bloom.upper()}.

STUDY MATERIAL:
{rag_labeled}

{syllabus_context}

DRAFT TO REVIEW:
{agent_a_output}

YOUR REVIEW TASKS:
1. Is the question factually grounded in the study material chunks? Check each claim.
2. Does it align with CO/LO codes from the syllabus?
3. Is it at the correct Bloom's level ({bloom})? If {bloom} is apply/analyze/evaluate/create, reject if it's just recall.
4. For MCQs: are all 4 distractors plausible? Is the correct answer unambiguous?
5. Does it start with forbidden patterns ("What is", "Define", "List")? Flag if bloom >= apply.
6. Does it reference the passage/document directly? (should NOT — must be standalone exam style)

OUTPUT JSON format (RAW JSON ONLY):
{{"score": <1-10>, "issues": ["issue1", "issue2"], "improved_question": <FULL QUESTION JSON IN SAME SCHEMA AS DRAFT including used_chunks and supporting_quotes>, "grounding_report": {{"factually_grounded": true/false, "missing_evidence": ["..."], "directness_flag": true/false}}}}

RULES:
- "improved_question" must be a COMPLETE question JSON object (not just text), with all citation fields.
- If the draft is good, return it as improved_question unchanged.
- Output RAW JSON ONLY. NO MARKDOWN. NO COMMENTS."""


def build_agent_c_prompt(
    subject, topic, question_type, difficulty, bloom, material_section,
    syllabus_context, sample_context, skill_context, format_instruction,
    attempt: int = 1, agent_a_output: str = "",
) -> str:
    """Build Agent C (Technician) prompt — alternative generation."""
    bloom_verbs = BLOOM_VERB_BANK.get(bloom, BLOOM_VERB_BANK["apply"])
    
    differentiation = ""
    if agent_a_output:
        differentiation = f"""
DIFFERENTIATION: Another agent already generated this draft:
{agent_a_output[:300]}...
You MUST generate a DIFFERENT question — different angle, different chunks, different cognitive demand."""

    bloom_instruction = ""
    if is_higher_order_bloom(bloom):
        bloom_instruction = f"""
BLOOM'S LEVEL: {bloom.upper()} — Use verbs like: {bloom_verbs}.
- Require multi-step reasoning or synthesis. NO simple recall.
- Use 2+ chunks for cross-concept questions."""

    return f"""You are an expert question paper setter for {subject}.

{material_section}

{syllabus_context}
{sample_context}
{skill_context}
{differentiation}

Generate exactly 1 {question_type} question about "{topic}".
Difficulty: {difficulty}
{bloom_instruction}

GROUNDING & CITATION RULES:
- Question MUST be based on the study material chunks above.
- Include "used_chunks" and "supporting_quotes" citing exact text.
- Do NOT hallucinate.

EXAM STYLE:
- STANDALONE exam question — no "based on the passage".
- Do NOT start with "What is"/"Define"/"List" for Bloom >= apply.
- Map to CO/LO codes if available.

OUTPUT: RAW JSON ONLY. No markdown, no wrapping.
CRITICAL: "question_text" must be a plain text string at the top level.

{format_instruction}"""


def build_chairman_prompt(
    rag_labeled, syllabus_context, agent_a_output, agent_b_output, agent_c_output, bloom,
) -> str:
    """Build Chairman prompt with structured selection, confidence scoring, and OBE alignment."""
    return f"""You are The Chairman of the Academic Council. Select the BEST question draft.

STUDY MATERIAL:
{rag_labeled}

{syllabus_context}

BLOOM'S LEVEL REQUIRED: {bloom.upper()}

DRAFT 1 (Logician): {agent_a_output}
REVIEW (Creative): {agent_b_output}
DRAFT 2 (Technician): {agent_c_output}

SELECTION CRITERIA (in priority order):
1. FACTUAL ACCURACY: Is it 100% grounded in the Study Material? Are cited chunks valid?
2. BLOOM ALIGNMENT: Does it match {bloom.upper()} level? (reject recall-only if bloom >= apply)
3. SYLLABUS ALIGNMENT: Does it map to CO/LO codes from the syllabus mapping above?
4. EXAM QUALITY: Standalone? No passage references? Plausible distractors (MCQ)?
5. CITATION QUALITY: Does it include used_chunks and supporting_quotes?

CONFIDENCE SCORING GUIDE:
- 8-10: All criteria met, strong grounding with 2+ chunk citations, correct Bloom level
- 5-7: Mostly correct but minor issues (weak distractors, single chunk, slightly off Bloom)
- 1-4: Major issues (hallucination, wrong Bloom, no citations, definition-only for higher Bloom)

If ALL drafts fail validation, set action to "regenerate".

OUTPUT JSON format (RAW JSON ONLY):
{{"action": "accept", "selected_from": "Agent A", "selected_question": <FULL QUESTION JSON>, "confidence_score": 7.5, "reasoning": "Brief selection rationale...", "obe_alignment": {{"blooms_level": "{bloom}", "blooms_justification": "This question requires the student to [verb] by [specific cognitive task], which maps to Bloom's {bloom} level because...", "co_codes": ["CO1"], "co_justification": "CO1 (full description): This question directly assesses this outcome because the student must...", "lo_codes": ["LO1.2"], "lo_justification": "LO1.2 (full description): The question targets this learning outcome by requiring the student to..."}}}}

CRITICAL REQUIREMENTS:
- "action" must be "accept" or "regenerate"
- "selected_question" must be a flat JSON with "question_text" as direct key
- "obe_alignment" is MANDATORY — you MUST justify Bloom's level, CO codes, and LO codes
- Use the ACTUAL CO/LO codes and descriptions from the SYLLABUS MAPPING above
- If no CO/LO codes are available in the syllabus, set codes to [] and write "No CO/LO codes provided in syllabus" in the justification
- Output RAW JSON ONLY. NO MARKDOWN. NO COMMENTS."""



# ─── (6) Confidence Post-Processing ───

def adjust_confidence(confidence: float, parsed_q, bloom: str, chunk_map: dict, validation_errors: list) -> float:
    """Adjust confidence score based on grounding quality."""
    score = confidence
    
    # Guard: parsed_q must be a dict — LLM sometimes returns a list
    if not isinstance(parsed_q, dict):
        parsed_q = None
    
    # Cap if validation errors exist
    if validation_errors:
        score = min(score, 4.0)
    
    # Bonus for good citations
    used_chunks = parsed_q.get("used_chunks", []) if parsed_q else []
    quotes = parsed_q.get("supporting_quotes", []) if parsed_q else []
    
    if len(used_chunks) >= 2:
        score = min(10.0, score + 0.5)
    if len(quotes) >= 2:
        score = min(10.0, score + 0.5)
    
    # Penalize missing citations for higher-order bloom
    if is_higher_order_bloom(bloom) and len(used_chunks) < 2:
        score = min(score, 5.0)
    
    return round(max(1.0, min(10.0, score)), 1)


# ─── (4) Fail-Fast JSON Repair ───

async def repair_json(model: str, bad_text: str, schema_instruction: str) -> str:
    """One-shot rapid attempt to fix malformed JSON."""
    repair_prompt = f"""The following JSON is malformed or incomplete:
{bad_text}

Fix it to match this schema exactly:
{schema_instruction}

Output RAW JSON ONLY. No explanation."""
    # Use a very low token cap for repair (400)
    fixed, _ = await call_ollama(model, repair_prompt, "You are a JSON repair specialist.", temperature=0.2, num_predict=400)
    return fixed


# ─── Main Generation Function (upgraded with parallelization & caps) ───

async def generate_single_question(
    question_type: str,
    topic: str,
    subject: str,
    difficulty: str,
    rag_context: str,
    available_models: list,
    syllabus_data: dict = None,
    sample_questions: str = "",
    skill_content: str = "",
    bloom_level: str = "",
    max_attempts: int = MAX_ATTEMPTS,
) -> dict:
    """Run the full Council pipeline for one question, with optimization and parallelization."""

    timings = {}
    models_used = {}

    # Resolve models
    agent_a_model = await resolve_model(AGENTS["logician"]["model"], available_models)
    agent_b_model = await resolve_model(AGENTS["creative"]["model"], available_models)
    agent_c_model = await resolve_model(AGENTS["technician"]["model"], available_models)
    chairman_model = await resolve_model(AGENTS["chairman"]["model"], available_models)

    models_used = {
        "agent_a": agent_a_model, "agent_b": agent_b_model,
        "agent_c": agent_c_model, "chairman": chairman_model,
    }

    # ─── Resolve Bloom Level ───
    bloom = resolve_bloom(bloom_level, syllabus_data, difficulty)
    
    # ─── (3) RAG Context Size Cap (Top 6) ───
    raw_chunks = [c.strip() for c in rag_context.split("\n\n") if c.strip()][:6]
    rag_labeled, chunk_map = format_rag_as_labeled_chunks("\n\n".join(raw_chunks))
    material_section = f"STUDY MATERIAL (PRIMARY SOURCE — cite chunks [C1]-[C{len(chunk_map)}]):\n{rag_labeled}" if rag_labeled else "STUDY MATERIAL: None available."

    if syllabus_data is None:
        syllabus_data = {}

    # ... (Syllabus/Context formatting remains same) ...
    syllabus_context = "No specific syllabus mapping provided."
    if syllabus_data:
        los = "\n".join([f"- {acc}: {desc}" for acc, desc in syllabus_data.get("los", {}).items()]) if syllabus_data.get("los") else "None"
        cos = "\n".join([f"- {acc}: {desc}" for acc, desc in syllabus_data.get("cos", {}).items()]) if syllabus_data.get("cos") else "None"
        blooms = "\n".join([f"- {level}: {weight}%" for level, weight in syllabus_data.get("bloom_distribution", {}).items()]) if syllabus_data.get("bloom_distribution") else "None"
        syllabus_context = f"SYLLABUS MAPPING:\nLearning Outcomes: {los}\nCourse Outcomes: {cos}\nBloom's: {blooms}\n"

    sample_context = f"\nSAMPLE QUESTIONS:\n{sample_questions}\n" if sample_questions else ""
    skill_context = f"\nGUIDELINES:\n{extract_skill_sections(skill_content)}\n" if skill_content else ""

    format_instruction = get_format_instruction(question_type, bloom)

    print(f"[Swarm] Generation - Topic: {topic}, Bloom: {bloom}, Top {len(chunk_map)} Chunks")

    best_result = None
    best_confidence = 0.0
    all_validation_errors = []

    for attempt in range(1, max_attempts + 1):
        attempt_timings = {}
        diversity_hint = f"\nAVOID REPEATING: {len(_session_questions)} previous Qs.\n" if _session_questions else ""

        # --- Phase 1: Agent A (Logician) ---
        # Temp 0.4 for stability, num_predict 800
        agent_a_prompt = build_agent_a_prompt(
            subject, topic, question_type, difficulty, bloom,
            material_section, syllabus_context, sample_context, skill_context,
            format_instruction, attempt, diversity_hint,
        )
        agent_a_output, agent_a_time = await call_ollama(
            agent_a_model, agent_a_prompt, AGENTS["logician"]["role"],
            temperature=0.4, num_predict=800
        )
        attempt_timings["agent_a"] = agent_a_time

        # ─── (1) Parallelize Agent B and Agent C ───
        
        agent_b_prompt = build_agent_b_prompt(
            question_type, topic, rag_labeled, syllabus_context, agent_a_output, bloom,
        )
        agent_c_prompt = build_agent_c_prompt(
            subject, topic, question_type, difficulty, bloom,
            material_section, syllabus_context, sample_context, skill_context,
            format_instruction, attempt, agent_a_output,
        )

        tasks = [
            call_ollama(agent_b_model, agent_b_prompt, AGENTS["creative"]["role"], temperature=0.7, num_predict=600),
            call_ollama(agent_c_model, agent_c_prompt, AGENTS["technician"]["role"], temperature=0.4, num_predict=800)
        ]
        
        (agent_b_output, b_time), (agent_c_output, c_time) = await asyncio.gather(*tasks)
        attempt_timings["agent_b"] = b_time
        attempt_timings["agent_c"] = c_time

        # --- Phase 4: Chairman ---
        chairman_prompt = build_chairman_prompt(
            rag_labeled, syllabus_context, agent_a_output, agent_b_output, agent_c_output, bloom,
        )
        chairman_output, chairman_time = await call_ollama(
            chairman_model, chairman_prompt, AGENTS["chairman"]["role"],
            temperature=0.4, num_predict=700
        )
        attempt_timings["chairman"] = chairman_time
        attempt_timings["total"] = sum(attempt_timings.values())

        # --- Parse & Repair ---
        parsed_chairman = parse_json(chairman_output)
        
        # ─── (4) Fail-Fast JSON Repair ───
        if not parsed_chairman and chairman_output.strip():
            print(f"[Swarm] Chairman JSON malformed. Triggering one-shot repair...")
            repaired = await repair_json(chairman_model, chairman_output, '{"action":"...","selected_question":{...},"confidence_score":...}')
            parsed_chairman = parse_json(repaired)
            if parsed_chairman:
                print(f"[Swarm] Repair successful.")
                chairman_output = repaired

        final_question = None
        confidence_score = 5.0
        selected_from = "Agent A"
        chairman_action = "accept"

        if parsed_chairman and isinstance(parsed_chairman, dict):
            final_question = parsed_chairman.get("selected_question")
            confidence_score = float(parsed_chairman.get("confidence_score", 5.0))
            selected_from = parsed_chairman.get("selected_from", "Agent A")
            chairman_action = parsed_chairman.get("action", "accept")
        else:
            final_question = parse_json(agent_a_output)
            selected_from = "Agent A (fallback)"

        # ─── Normalize: LLM sometimes wraps the question in a list ───
        if isinstance(final_question, list):
            # Extract first dict from the list
            final_question = next((item for item in final_question if isinstance(item, dict)), None)

        # Validate the selected question
        validation_errors = validate_question_output(
            final_question, question_type, bloom, difficulty, chunk_map,
        )

        # Dedup check
        qt = ""
        if final_question and isinstance(final_question, dict):
            qt = final_question.get("question_text") or final_question.get("question") or ""
        if qt and is_duplicate(qt):
            validation_errors.append("Duplicate of previous question in this session")

        # Adjust confidence
        confidence_score = adjust_confidence(confidence_score, final_question, bloom, chunk_map, validation_errors)

        # Build result
        attempt_result = {
            "question": final_question,
            "confidence_score": confidence_score,
            "selected_from": selected_from,
            "agent_a_draft": agent_a_output,
            "agent_b_review": agent_b_output,
            "agent_c_draft": agent_c_output,
            "chairman_output": chairman_output,
            "rag_context_used": rag_context,
            "timings": attempt_timings,
            "models_used": models_used,
            "bloom_level": bloom,
            "attempt": attempt,
            "validation_errors": validation_errors,
        }

        print(f"[Swarm] Attempt {attempt}/{max_attempts}: confidence={confidence_score}, errors={len(validation_errors)}, action={chairman_action}")
        if validation_errors:
            print(f"[Swarm] Rejection Reasons: {validation_errors}")

        # Accept if valid
        if not validation_errors and chairman_action == "accept":
            if qt:
                register_in_session(qt)
            # Accumulate timings across attempts
            if best_result:
                for k, v in attempt_timings.items():
                    attempt_result["timings"][k] = attempt_result["timings"].get(k, 0) + best_result["timings"].get(k, 0)
            return attempt_result

        # Track best attempt
        all_validation_errors.extend(validation_errors)
        if confidence_score > best_confidence:
            best_confidence = confidence_score
            best_result = attempt_result

        if attempt < max_attempts:
            print(f"[Swarm] Regenerating (attempt {attempt + 1})... Reason: {validation_errors[0] if validation_errors else 'Chairman REGENERATE'}")


    # All attempts exhausted — return best with low confidence
    print(f"[Swarm] All {max_attempts} attempts exhausted. Returning best (confidence={best_confidence})")
    if best_result:
        best_result["confidence_score"] = min(best_result["confidence_score"], 4.0)
        best_result["validation_errors"] = all_validation_errors[:5]
        qt = ""
        if best_result.get("question") and isinstance(best_result["question"], dict):
            qt = best_result["question"].get("question_text") or best_result["question"].get("question") or ""
        if qt:
            register_in_session(qt)
        return best_result

    # Absolute fallback
    return {
        "question": None, "confidence_score": 1.0, "selected_from": "None",
        "agent_a_draft": "", "agent_b_review": "", "agent_c_draft": "",
        "chairman_output": "", "rag_context_used": rag_context,
        "timings": {"total": 0}, "models_used": models_used,
        "bloom_level": bloom, "attempt": max_attempts,
        "validation_errors": ["All generation attempts failed"],
    }
