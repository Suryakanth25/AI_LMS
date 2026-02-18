import httpx
import json
import time

OLLAMA_BASE = "http://localhost:11434"

AGENTS = {
    "logician": {
        "model": "phi3.5",
        "role": "Strict adherence to facts from the study material. Generate questions grounded in source content.",
    },
    "creative": {
        "model": "gemma2:2b",
        "role": "Review questions for accuracy, clarity, and suggest improvements while staying true to source material.",
    },
    "technician": {
        "model": "qwen2.5:3b",
        "role": "Generate precise, well-structured questions with proper formatting and technical accuracy.",
    },
    "chairman": {
        "model": "phi3.5",
        "role": "Final arbiter. Score drafts, select the best, assign confidence score based on factual accuracy.",
    },
}


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
    # Exact match
    if preferred in available:
        return preferred
    # Prefix match (e.g. "phi3.5" matches "phi3.5:latest")
    for m in available:
        if m.startswith(preferred) or preferred.startswith(m.split(":")[0]):
            return m
    # Fallback to first available
    if available:
        return available[0]
    return preferred


async def call_ollama(model: str, prompt: str, system: str = "") -> tuple[str, float]:
    """Call Ollama /api/generate and return (response_text, elapsed_seconds)."""
    start = time.time()
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 2048},
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
    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try to find JSON object or array in the text
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        # Find matching closing bracket
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
    """Extract only Sections 2-4 from a SKILL.md document for prompt injection.
    Returns the CO reference, format rules, and faculty rules sections (~300 words).
    Skips Section 1 (subject scope) and Section 5 (examples)."""
    if not skill_content:
        return ""
    
    lines = skill_content.split("\n")
    include = False
    result = []
    
    for line in lines:
        stripped = line.strip().lower()
        # Start including from Section 2
        if "## 2" in stripped or "co-bloom" in stripped or "co to bloom" in stripped or "co reference" in stripped:
            include = True
        # Stop including at Section 5
        if "## 5" in stripped or "gold example" in stripped:
            include = False
            break
        if include:
            result.append(line)
    
    extracted = "\n".join(result).strip()
    
    # Fallback: if extraction found nothing meaningful, return truncated content
    if len(extracted) < 50:
        # Return the first 1500 chars as fallback (better than nothing)
        return skill_content[:1500]
    
    return extracted


async def generate_single_question(
    question_type: str,
    topic: str,
    subject: str,
    difficulty: str,
    rag_context: str,
    available_models: list,
    syllabus_data: dict = {},
    sample_questions: str = "",
    skill_content: str = ""
) -> dict:
    """Run the full Council pipeline for one question."""

    timings = {}
    models_used = {}

    # Resolve models
    agent_a_model = await resolve_model(AGENTS["logician"]["model"], available_models)
    agent_b_model = await resolve_model(AGENTS["creative"]["model"], available_models)
    agent_c_model = await resolve_model(AGENTS["technician"]["model"], available_models)
    chairman_model = await resolve_model(AGENTS["chairman"]["model"], available_models)

    models_used = {
        "agent_a": agent_a_model,
        "agent_b": agent_b_model,
        "agent_c": agent_c_model,
        "chairman": chairman_model,
    }

    # Format Syllabus Context
    syllabus_context = "No specific syllabus mapping provided."
    if syllabus_data:
        los = "\n".join([f"- {acc}: {desc}" for acc, desc in syllabus_data.get("los", {}).items()]) if syllabus_data.get("los") else "None"
        cos = "\n".join([f"- {acc}: {desc}" for acc, desc in syllabus_data.get("cos", {}).items()]) if syllabus_data.get("cos") else "None"
        blooms = "\n".join([f"- {level}: {weight}%" for level, weight in syllabus_data.get("bloom_distribution", {}).items()]) if syllabus_data.get("bloom_distribution") else "None"
        syllabus_context = f"""
SYLLABUS MAPPING:
Learning Outcomes (LOs):
{los}
Course Outcomes (COs):
{cos}
Cognitive Weightage (Bloom's):
{blooms}
"""

    sample_context = ""
    if sample_questions:
        sample_context = f"""
SAMPLE QUESTIONS (Mimic style and depth):
{sample_questions}
"""

    skill_context = ""
    if skill_content:
        # Only inject Sections 2-4 (CO reference, format rules, faculty rules)
        filtered_skill = extract_skill_sections(skill_content)
        skill_context = f"""
GENERATION GUIDELINES (from faculty training):
{filtered_skill}
Apply these guidelines strictly to avoid previous mistakes and align with faculty expectations.
"""

    # Helper: specific format instructions
    format_instruction = ""
    if question_type == "MCQ":
        format_instruction = """Output JSON format:
{"question_text": "Question here...", "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"], "correct_answer": "B", "explanation": "Why B is correct..."}"""
    elif question_type == "Short Notes":
        format_instruction = """Output JSON format:
{"question_text": "Question here...", "key_points": ["Point 1", "Point 2", "Point 3"], "marks": 5}"""
    elif question_type == "Essay":
        format_instruction = """Output JSON format:
{"question_text": "Question here...", "expected_structure": ["Intro...", "Body...", "Conclusion..."], "marks": 10, "word_limit": 500}"""

    # Ensure material context is clear
    material_section = f"STUDY MATERIAL (PRIMARY SOURCE):\n{rag_context}" if rag_context else "STUDY MATERIAL: None available. Rely on general academic knowledge aligned with syllabus."

    print(f"DEBUG: Swarm Generation - Subject: {subject}, Topic: {topic}")
    print(f"DEBUG: RAG Context Length: {len(rag_context)} chars")
    if len(rag_context) > 50:
        print(f"DEBUG: RAG Content Check: {rag_context[:100]}... [matches expected?]")
    else:
        print(f"DEBUG: ⚠️ RAG Context is EMPTY or too short!")

    # --- Phase 1: Agent A (Logician) generates ---
    agent_a_prompt = f"""You are an expert question paper setter for {subject}.

{material_section}

{syllabus_context}
{sample_context}
{skill_context}

Generate exactly 1 {question_type} question about "{topic}".
Difficulty: {difficulty}

RULES:
- Question MUST be derived from the STUDY MATERIAL provided above (if available).
- Align with the Learning Outcomes and Course Outcomes if provided.
- Adhere to the cognitive level appropriate for the difficulty and weightage.
- Do NOT hallucinate facts not in the material.
- Output RAW JSON ONLY. No markdown, no 'Here is the JSON', no wrapping.
- CRITICAL: "question_text" must be a plain text string at the top level of your JSON. Never nest the question inside wrapper objects.

{format_instruction}"""

    agent_a_output, agent_a_time = await call_ollama(
        agent_a_model, agent_a_prompt, AGENTS["logician"]["role"]
    )
    timings["agent_a"] = agent_a_time

    # --- Phase 2: Agent B (Creative) reviews Agent A ---
    agent_b_prompt = f"""Review this {question_type} question for "{topic}".

STUDY MATERIAL: {rag_context}
{syllabus_context}
DRAFT: {agent_a_output}

Evaluate: factual accuracy vs material, clarity, difficulty, option quality, alignment with LOs/COs.
OUTPUT JSON format: {{"score":<1-10>, "issues":["..."], "improved_version_text": "...", "factually_grounded":<bool>}}
RULES:
- "improved_version_text" should be the full text of the improved question (not JSON).
- CRITICAL: "improved_version_text" must be a simple string. Do NOT output a JSON object here.
- Output RAW JSON ONLY.
- NO COMMENTS inside the JSON.
- NO MARKDOWN."""

    agent_b_output, agent_b_time = await call_ollama(
        agent_b_model, agent_b_prompt, AGENTS["creative"]["role"]
    )
    timings["agent_b"] = agent_b_time

    # --- Phase 3: Agent C (Technician) generates alternative ---
    agent_c_prompt = f"""You are an expert question paper setter for {subject}.

STUDY MATERIAL CONTEXT:
{rag_context}

{syllabus_context}
{sample_context}
{skill_context}

Generate exactly 1 {question_type} question about "{topic}".
Difficulty: {difficulty}

RULES:
- Question MUST be based on the study material above
- Align with the Learning Outcomes and Course Outcomes if provided
- Do NOT hallucinate facts not in the material
- Output RAW JSON ONLY. No markdown, no wrapping.
- CRITICAL: "question_text" must be a plain text string at the top level.
- NO COMMENTS in JSON.

{format_instruction}"""

    agent_c_output, agent_c_time = await call_ollama(
        agent_c_model, agent_c_prompt, AGENTS["technician"]["role"]
    )
    timings["agent_c"] = agent_c_time

    # --- Phase 4: Chairman selects best ---
    chairman_prompt = f"""You are The Chairman of the Academic Council. Your role is to select the absolute BEST question draft and provide a rigorous pedagogical justification.

STUDY MATERIAL: {rag_context}
{syllabus_context}

DRAFT 1 (Logician): {agent_a_output}
REVIEW: {agent_b_output}
DRAFT 2 (Technician): {agent_c_output}

Your Selection Criteria:
1. FACTUAL ACCURACY: Is the question 100% grounded in the Study Material?
2. SYLLABUS ALIGNMENT: Does it map perfectly to the provided Course Outcomes (COs) and Learning Outcomes (LOs)?
3. PEDAGOGICAL DEPTH: Is the language clear? Does it match the intended difficulty and Bloom's level?

OUTPUT JSON format: {{"selected_question":<question json>,"confidence_score":<1.0-10.0>,"selected_from":"Agent A/Agent C/Combined","reasoning":"[PROOF OF ALIGNMENT] Provide a detailed paragraph (100+ words). You MUST cite specific CO codes (e.g., CO-1) and LO codes (e.g., LO-1.1) from the syllabus context provided above. Explain WHY this specific question is the most pedagogically sound choice and how it relates to the study material facts."}}

RULES:
- "reasoning" MUST be a detailed, professional paragraph. Do not be brief.
- citation of CO/LO codes is MANDATORY.
- Output RAW JSON ONLY.
- NO COMMENTS inside the JSON.
- NO MARKDOWN.
- CRITICAL: "selected_question" must be a flat JSON object with "question_text" as a direct key. Never double-wrap it."""

    chairman_output, chairman_time = await call_ollama(
        chairman_model, chairman_prompt, AGENTS["chairman"]["role"]
    )
    timings["chairman"] = chairman_time

    timings["total"] = (
        timings["agent_a"] + timings["agent_b"] + timings["agent_c"] + timings["chairman"]
    )

    # --- Parse Chairman output ---
    parsed_chairman = parse_json(chairman_output)
    final_question = None
    confidence_score = 5.0
    selected_from = "Agent A"

    if parsed_chairman and isinstance(parsed_chairman, dict):
        final_question = parsed_chairman.get("selected_question")
        confidence_score = float(parsed_chairman.get("confidence_score", 5.0))
        selected_from = parsed_chairman.get("selected_from", "Agent A")
    else:
        # Fallback: use Agent A draft
        final_question = parse_json(agent_a_output)
        confidence_score = 5.0
        selected_from = "Agent A"

    return {
        "question": final_question,
        "confidence_score": confidence_score,
        "selected_from": selected_from,
        "agent_a_draft": agent_a_output,
        "agent_b_review": agent_b_output,
        "agent_c_draft": agent_c_output,
        "chairman_output": chairman_output,
        "rag_context_used": rag_context,
        "timings": timings,
        "models_used": models_used,
    }
