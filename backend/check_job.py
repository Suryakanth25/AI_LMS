import requests
import json

API_BASE = "http://127.0.0.1:8000/api"
# Hardcode job ID based on logs
JOB_ID = 6
print(f"Checking Job ID: {JOB_ID}")

res = requests.get(f"{API_BASE}/generate/job/{JOB_ID}")
print(json.dumps(res.json(), indent=2))

res = requests.get(f"{API_BASE}/generate/job/{JOB_ID}/questions")
questions = res.json()
print(f"Generated {len(questions)} questions")
for q in questions:
    print(f"- {repr(q['text'])} ({q['question_type']}) - Confidence: {q['confidence_score']}")
    # print(q) # Raw debug
