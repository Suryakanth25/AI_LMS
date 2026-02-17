import requests, json

# Fetch each question detail via vetting endpoint
for qid in range(1, 5):
    q = requests.get(f"http://localhost:8000/api/vetting/question/{qid}").json()
    print(f"\n{'='*60}")
    print(f"Q{q['id']}: {q['question_type']} | Confidence: {q['confidence_score']} | {q['difficulty']}")
    print(f"Marks: {q['marks']} | Time: {q['generation_time_seconds']:.1f}s | Selected: {q['selected_from']}")
    print(f"{'='*60}")
    print(f"Question: {q['text']}")
    if q['options']:
        print("Options:")
        for opt in q['options']:
            print(f"  {opt}")
        print(f"Correct Answer: {q['correct_answer']}")
    print(f"\nStatus: {q['status']}")

# Test vetting submit
print("\n\n=== Testing Vetting Submit ===")
r = requests.post("http://localhost:8000/api/vetting/submit", json={
    "question_id": 1,
    "action": "approved",
    "feedback": "Good question, well structured"
}).json()
print(json.dumps(r, indent=2))

# Check updated queue
vq = requests.get("http://localhost:8000/api/vetting/queue?status=pending").json()
print(f"Remaining pending: {len(vq)}")

vq2 = requests.get("http://localhost:8000/api/vetting/queue?status=approved").json()
print(f"Approved: {len(vq2)}")
