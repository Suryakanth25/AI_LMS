"""Quick functional test for swarm.py V2 functions."""
from services.swarm import (
    resolve_bloom, format_rag_as_labeled_chunks, validate_question_output,
    is_duplicate, register_in_session, clear_session, adjust_confidence,
    is_higher_order_bloom, build_agent_a_prompt, get_format_instruction,
)

print("=== Bloom Resolution ===")
assert resolve_bloom("application") == "apply"
assert resolve_bloom("", None, "Hard") == "analyze"
assert resolve_bloom("", None, "Easy") == "understand"
assert resolve_bloom("", None, "Medium") == "apply"
assert is_higher_order_bloom("apply") == True
assert is_higher_order_bloom("understand") == False
print("  [PASS]")

print("=== Labeled Chunks ===")
labeled, cmap = format_rag_as_labeled_chunks("Chunk A about ORN.\n\nChunk B about HBO therapy.")
assert len(cmap) == 2
assert "C1" in cmap and "C2" in cmap
assert "[C1]" in labeled and "[C2]" in labeled
print(f"  {len(cmap)} chunks, IDs: {list(cmap.keys())} [PASS]")

print("=== Validation Gate ===")
# Direct question that should fail for Bloom=apply
e1 = validate_question_output(
    {"question_text": "Define ORN", "used_chunks": ["C1"], "options": ["A.x","B.y","C.z","D.w"], "correct_answer": "B"},
    "MCQ", "apply", "Hard", cmap,
)
assert any("too direct" in e.lower() or "direct" in e.lower() for e in e1), f"Expected directness error: {e1}"
print(f"  Direct question: {len(e1)} errors [PASS]")

# Good question
e2 = validate_question_output(
    {"question_text": "Compare HBO therapy vs surgical debridement for ORN management",
     "options": ["A. x","B. y","C. z","D. w"], "correct_answer": "B",
     "used_chunks": ["C1","C2"], "supporting_quotes": []},
    "MCQ", "apply", "Hard", cmap,
)
assert len(e2) == 0, f"Unexpected errors: {e2}"
print(f"  Good question: {len(e2)} errors [PASS]")

# Missing options
e3 = validate_question_output(
    {"question_text": "Analyze the role of HBO", "used_chunks": ["C1","C2"]},
    "MCQ", "apply", "Hard", cmap,
)
assert any("4 options" in e for e in e3)
print(f"  Missing options: {len(e3)} errors [PASS]")

print("=== Dedup ===")
clear_session()
register_in_session("What is ORN?")
assert is_duplicate("What is ORN?") == True
assert is_duplicate("Compare HBO therapy approaches") == False
print("  [PASS]")

print("=== Confidence Adjustment ===")
c1 = adjust_confidence(8.0, {"used_chunks": ["C1","C2"], "supporting_quotes": [{"chunk_id":"C1","quote":"x"},{"chunk_id":"C2","quote":"y"}]}, "apply", cmap, [])
assert c1 >= 8.0, f"Expected >= 8.0, got {c1}"
c2 = adjust_confidence(8.0, {"used_chunks": []}, "apply", cmap, ["missing chunks"])
assert c2 <= 4.0, f"Expected <= 4.0, got {c2}"
print(f"  Good={c1}, Bad={c2} [PASS]")

print("=== Prompt Building ===")
prompt = build_agent_a_prompt(
    "Dentistry", "ORN", "MCQ", "Hard", "analyze",
    "[C1] ORN text...", "LOs: LO-1", "", "", get_format_instruction("MCQ", "analyze"),
    attempt=2,
)
assert "BLOOM'S LEVEL: ANALYZE" in prompt
assert "DIVERSITY" in prompt
assert "used_chunks" in prompt
print(f"  Prompt length: {len(prompt)} chars [PASS]")

print("\n=== ALL SWARM V2 TESTS PASSED ===")
