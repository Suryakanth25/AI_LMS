import asyncio
from services.swarm import generate_single_question

async def main():
    print("--- [Swarm V2] Starting test generation for logs ---")
    mock_rag = """
[C1] Oral radionecrosis (ORN) of the jaws is a serious complication following radiation therapy for head and neck malignancies. 
The condition is characterized by non-healing, exposed bone in a field of previous radiation.
[C2] Management of ORN depends on the severity. Early stages may be managed with conservative therapy including irrigation and antibiotics.
[C3] More advanced cases require hyperbaric oxygen therapy (HBO) and surgical intervention such as debridement or resection.
"""
    mock_syllabus = {
        "los": {"LO-1.1": "Explain the pathogenesis of ORN"},
        "cos": {"CO-4": "Assess complications of radiotherapy in the oral cavity"}
    }
    
    # We pass an empty list for models to use fallbacks/defaults
    result = await generate_single_question(
        question_type="MCQ",
        topic="Management of ORN",
        subject="Dentistry",
        difficulty="Hard",
        rag_context=mock_rag,
        available_models=[], # Will use resolve_model fallbacks
        syllabus_data=mock_syllabus,
        bloom_level="analyze"
    )
    
    print("\n--- Generation Complete ---")
    print(f"Selected From: {result.get('selected_from')}")
    print(f"Confidence: {result.get('confidence_score')}")
    print(f"Attempts: {result.get('attempt')}")
    print(f"Validation Errors: {result.get('validation_errors')}")

if __name__ == "__main__":
    asyncio.run(main())
