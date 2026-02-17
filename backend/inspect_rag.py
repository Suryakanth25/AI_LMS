import requests
import json

API_BASE = "http://127.0.0.1:8000/api"
JOB_ID = 4

print(f"--- Inspecting RAG Context for Job {JOB_ID} ---\n")

# Fetch generated questions
res = requests.get(f"{API_BASE}/generate/job/{JOB_ID}/questions")
questions = res.json()

for idx, q in enumerate(questions):
    print(f"Question {idx+1} ({q['question_type']}):")
    print(f"Q: {q['text']}")
    print(f"\n[RAG DATA USED]")
    # The 'rag_context_used' field stores the specific text chunks retrieved
    context = q.get('rag_context_used', 'No context recorded')
    print(f"{context}")
    print("-" * 60 + "\n")
