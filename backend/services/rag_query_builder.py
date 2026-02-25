"""
RAG Query Builder v2 — Generate multiple query variants from structured inputs.
No raw user query needed — queries are built from topic, LO, CO, bloom level, etc.
"""
from dataclasses import dataclass


@dataclass
class QueryVariant:
    """A single query variant with metadata about how it was generated."""
    text: str
    strategy: str   # e.g. "semantic", "bloom_verb", "keyword", "question_type"
    weight: float   # Relative importance (0.0–1.0)


# ─── Bloom's Taxonomy Verb Mapping ───

BLOOM_VERBS = {
    "knowledge": [
        "define", "list", "identify", "describe", "name", "recall", "state",
        "recognize", "label", "outline",
    ],
    "comprehension": [
        "explain", "summarize", "interpret", "classify", "compare",
        "distinguish", "discuss", "illustrate", "paraphrase",
    ],
    "application": [
        "apply", "demonstrate", "implement", "solve", "use", "calculate",
        "execute", "practice", "operate", "employ",
    ],
    "analysis": [
        "analyze", "differentiate", "examine", "investigate", "categorize",
        "compare and contrast", "deconstruct", "organize", "dissect",
    ],
    "synthesis": [
        "design", "create", "construct", "develop", "formulate", "propose",
        "compose", "integrate", "plan", "devise",
    ],
    "evaluation": [
        "evaluate", "assess", "justify", "critique", "judge", "appraise",
        "argue", "defend", "recommend", "prioritize",
    ],
}

# Normalize keys for flexible matching
_BLOOM_ALIAS = {
    "remember": "knowledge",
    "understand": "comprehension",
    "apply": "application",
    "analyse": "analysis",
    "analyze": "analysis",
    "create": "synthesis",
    "evaluate": "evaluation",
}


def _resolve_bloom(level: str) -> str:
    """Resolve various bloom level names to canonical keys."""
    if not level:
        return "comprehension"
    lower = level.lower().strip()
    if lower in BLOOM_VERBS:
        return lower
    return _BLOOM_ALIAS.get(lower, "comprehension")


def _extract_key_nouns(text: str) -> list[str]:
    """Extract likely key nouns/phrases from LO or CO text (simple heuristic)."""
    import re
    
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
        'and', 'or', 'but', 'not', 'no', 'if', 'that', 'this', 'these',
        'those', 'it', 'its', 'able', 'using', 'use', 'based', 'given',
        'students', 'student', 'learner', 'understand', 'demonstrate',
        'describe', 'explain', 'identify', 'apply', 'analyze', 'evaluate',
    }
    
    # Extract words 3+ chars, skip stopwords
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    key_words = [w for w in words if w not in stopwords]
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for w in key_words:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    
    return unique[:8]  # Top 8 key terms


# ─── Query Generation ───

def build_query_variants(
    topic_name: str,
    lo_text: str = "",
    co_text: str = "",
    bloom_level: str = "",
    difficulty: str = "Medium",
    question_type: str = "MCQ",
) -> list[QueryVariant]:
    """
    Generate 4–8 diverse query variants from structured educational inputs.
    
    Returns a list of QueryVariant objects, each with text, strategy name, and weight.
    """
    variants = []
    bloom_key = _resolve_bloom(bloom_level)
    verbs = BLOOM_VERBS.get(bloom_key, BLOOM_VERBS["comprehension"])
    
    # ─── Strategy 1: Semantic (topic + LO combined) ───
    if lo_text:
        variants.append(QueryVariant(
            text=f"{topic_name}: {lo_text}",
            strategy="semantic_topic_lo",
            weight=1.0,
        ))
    else:
        variants.append(QueryVariant(
            text=topic_name,
            strategy="semantic_topic",
            weight=0.9,
        ))
    
    # ─── Strategy 2: Semantic (topic + CO context) ───
    if co_text:
        variants.append(QueryVariant(
            text=f"{topic_name} in context of {co_text}",
            strategy="semantic_topic_co",
            weight=0.8,
        ))
    
    # ─── Strategy 3: Bloom verb queries (2–3 variants) ───
    # Pick 2 bloom verbs and construct action-oriented queries
    selected_verbs = verbs[:3]
    for i, verb in enumerate(selected_verbs[:2]):
        target = lo_text if lo_text else topic_name
        bloom_query = f"{verb.capitalize()} {target}"
        variants.append(QueryVariant(
            text=bloom_query,
            strategy=f"bloom_verb_{verb}",
            weight=0.7 - (i * 0.05),
        ))
    
    # ─── Strategy 4: Keyword-heavy queries ───
    # Extract key nouns from LO/CO text and build keyword search strings
    source_text = lo_text or co_text or topic_name
    key_nouns = _extract_key_nouns(source_text)
    
    if key_nouns:
        # Dense keyword query
        keyword_query = " ".join(key_nouns[:5])
        variants.append(QueryVariant(
            text=keyword_query,
            strategy="keyword_dense",
            weight=0.6,
        ))
        
        # Topic + key terms
        if len(key_nouns) >= 3:
            topic_keyword = f"{topic_name} {' '.join(key_nouns[:3])}"
            variants.append(QueryVariant(
                text=topic_keyword,
                strategy="keyword_topic_terms",
                weight=0.65,
            ))
    
    # ─── Strategy 5: Question-type specific ───
    type_templates = {
        "MCQ": "factual concepts definitions about {topic}",
        "Short Notes": "key points important aspects of {topic}",
        "Essay": "detailed comprehensive explanation of {topic} including significance applications",
    }
    template = type_templates.get(question_type, type_templates["MCQ"])
    variants.append(QueryVariant(
        text=template.format(topic=topic_name),
        strategy=f"question_type_{question_type.lower().replace(' ', '_')}",
        weight=0.5,
    ))
    
    # ─── Strategy 6: Difficulty-aware (optional) ───
    if difficulty.lower() == "hard" and lo_text:
        variants.append(QueryVariant(
            text=f"advanced complex aspects of {topic_name}: clinical applications complications",
            strategy="difficulty_hard",
            weight=0.55,
        ))
    elif difficulty.lower() == "easy":
        variants.append(QueryVariant(
            text=f"basic introduction fundamentals of {topic_name}",
            strategy="difficulty_easy",
            weight=0.55,
        ))
    
    return variants
