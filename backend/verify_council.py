import requests
import time
import json
import os

API_BASE = "http://127.0.0.1:8000/api"

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def check_backend():
    try:
        requests.get(f"http://127.0.0.1:8000/health")
        return True
    except:
        return False

def run_verification():
    print_header("Step 1: Setup & Creation")
    
    # 1. Create Subject
    print("Creating Subject 'OS Verification'...")
    res = requests.post(f"{API_BASE}/subjects/", json={"name": "OS Verification", "code": "SCAL-001"})
    if res.status_code == 200:
        subject = res.json()
        subject_id = subject['id']
        print(f"✅ Subject Created: {subject['name']} (ID: {subject_id})")
    elif res.status_code == 400 and "already exists" in res.text:
        print("⚠️ Subject already exists. Fetching existing...")
        # Fetch all subjects and find the one with the code
        all_subs = requests.get(f"{API_BASE}/subjects/").json()
        subject = next((s for s in all_subs if s['code'] == "SCAL-001"), None)
        if subject:
            subject_id = subject['id']
            print(f"✅ Subject Found: {subject['name']} (ID: {subject_id})")
        else:
            print("❌ Could not find existing subject.")
            return
    else:
        print(f"Failed to create subject: {res.text}")
        return

    # 1b. Ensure Units and Topics exist
    print("\nEnsuring Units and Topics...")
    if subject.get('unit_count', 0) == 0:
        # Create Unit
        res = requests.post(f"{API_BASE}/subjects/{subject_id}/units", json={
            "name": "Memory Management",
            "unit_number": 1
        })
        if res.status_code != 200:
            print(f"❌ Failed to create unit: {res.text}")
            return
        unit_id = res.json()['id']
        print(f"✅ Unit Created: {res.json()['name']}")
        
        # Create Topic
        res = requests.post(f"{API_BASE}/units/{unit_id}/topics", json={
            "title": "Paging"
        })
        if res.status_code != 200:
            print(f"❌ Failed to create topic: {res.text}")
            return
        print(f"✅ Topic Created: {res.json()['title']}")
    else:
        print("✅ Subject already has units.")

    # 2. Upload Material
    print("\nUploading Study Material...")
    file_path = "sample_material.txt"
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("Sample content for paging.")
            
    with open(file_path, "rb") as f:
        res = requests.post(
            f"{API_BASE}/subjects/{subject_id}/upload-material",
            files={"file": ("paging.txt", f, "text/plain")}
        )
    print(f"✅ Material Uploaded: {res.json().get('filename')}")

    # 3. Create Rubric
    print("\nCreating Rubric (2 MCQ, 2 Short, 1 Essay)...")
    rubric_data = {
        "name": "Verification Exam",
        "exam_type": "quiz",
        "duration": 30,
        "total_marks": 20,
        "mcq_count": 2, "mcq_marks": 2,
        "short_count": 2, "short_marks": 3,
        "essay_count": 1, "essay_marks": 10
    }
    res = requests.post(f"{API_BASE}/rubrics/", json=rubric_data)
    rubric = res.json()
    rubric_id = rubric['id']
    print(f"✅ Rubric Created: {rubric['name']} (ID: {rubric_id})")

    print_header("Step 2: Generation")
    # 4. Start Generation
    print("Starting Generation Job...")
    res = requests.post(f"{API_BASE}/generate/", json={
        "rubric_id": rubric_id,
        "subject_id": subject_id
    })
    job = res.json()
    job_id = job['job_id']
    print(f"🚀 Job Started (ID: {job_id}). Polling for results...")

    # 5. Poll
    start_time = time.time()
    while True:
        res = requests.get(f"{API_BASE}/generate/job/{job_id}")
        data = res.json()
        status = data['status']
        progress = data.get('progress', 0)
        
        print(f"\rProgress: {progress}% ({status})", end="")
        
        if status == 'completed':
            print("\n✅ Generation Completed!")
            break
        elif status == 'failed':
            print(f"\n❌ Generation Failed: {data.get('error_message')}")
            return
        
        time.sleep(1)

    print_header("Step 3: Verification Report")
    
    # 6. Fetch Questions
    res = requests.get(f"{API_BASE}/generate/job/{job_id}/questions")
    questions = res.json()
    
    # 7. Fetch Benchmarks
    res = requests.get(f"{API_BASE}/benchmarks/job/{job_id}")
    benchmarks = res.json()

    print(f"Total Questions Generated: {len(questions)}")
    print(f"Average Confidence Score: {benchmarks.get('avg_confidence', 'N/A')}")
    print(f"Total Time Taken: {benchmarks.get('total_time_seconds', 0):.2f}s")
    
    print("\n--- GENERATED QUESTIONS ---")
    for q in questions:
        print(f"\n[{q['type'].upper()}] (Confidence: {q['confidence_score']}/10)")
        print(f"Q: {q['content']}")
        if q['type'] == 'mcq':
            options = json.loads(q['options']) if isinstance(q['options'], str) else q['options']
            for opt in options:
                print(f" - {opt}")
        print(f"A: {q['correct_answer']}")

    print("\n--- BENCHMARK BREAKDOWN ---")
    print(f"Agent A (Drafting): {benchmarks.get('phase_timings', {}).get('drafting', 0):.2f}s")
    print(f"Agent B (Review):   {benchmarks.get('phase_timings', {}).get('review', 0):.2f}s")
    print(f"Agent C (Refining): {benchmarks.get('phase_timings', {}).get('refinement', 0):.2f}s")
    print(f"Agent D (Finalize): {benchmarks.get('phase_timings', {}).get('finalization', 0):.2f}s")

if __name__ == "__main__":
    if check_backend():
        run_verification()
    else:
        print("❌ Backend is not reachable. Please start it first.")
