import requests
import time
import sys

API_BASE = "http://127.0.0.1:8000"

def get_subjects():
    try:
        res = requests.get(f"{API_BASE}/api/subjects/")
        return res.json()
    except Exception as e:
        print(f"Error connecting to backend: {e}")
        return []

def get_rubrics():
    return requests.get(f"{API_BASE}/api/rubrics/").json()

def start_generation(subject_id, rubric_id):
    res = requests.post(f"{API_BASE}/api/generate/", json={"rubric_id": rubric_id, "subject_id": subject_id})
    if res.status_code != 200:
        print(f"Error: {res.text}")
        sys.exit(1)
    return res.json()

def poll_job(job_id):
    while True:
        res = requests.get(f"{API_BASE}/api/generate/job/{job_id}")
        data = res.json()
        status = data.get("status")
        progress = data.get("progress", 0)
        total = data.get("total_questions_requested", 100)
        
        # Simple progress bar
        bar_len = 30
        filled = int(bar_len * progress / 100)
        bar = "=" * filled + "-" * (bar_len - filled)
        sys.stdout.write(f"\r[{bar}] {progress}% ({status})")
        sys.stdout.flush()

        if status == "completed":
            print("\nGeneration Complete!")
            return data
        if status == "failed":
            print(f"\nJob Failed: {data.get('error')}")
            return None
        
        time.sleep(1)

def main():
    print("--- Council CLI Generator ---")
    
    # 1. Select Subject
    subjects = get_subjects()
    if not subjects:
        print("No subjects found or backend down.")
        return

    print("\nAvailable Subjects:")
    for i, s in enumerate(subjects):
        print(f"{i+1}. {s['name']} (ID: {s['id']}) - {s.get('material_count', 0)} materials")
    
    s_idx = int(input("\nSelect Subject (1-N): ")) - 1
    subject = subjects[s_idx]
    print(f"Selected: {subject['name']}")

    # 2. Select Rubric
    rubrics = get_rubrics()
    if not rubrics:
        print("No rubrics found.")
        return

    print("\nAvailable Rubrics:")
    for i, r in enumerate(rubrics):
        print(f"{i+1}. {r['name']} (ID: {r['id']})")
    
    r_idx = int(input("\nSelect Rubric (1-N): ")) - 1
    rubric = rubrics[r_idx]
    print(f"Selected: {rubric['name']}")

    # 3. Generate
    print(f"\nStarting generation for {subject['name']} with {rubric['name']}...")
    job = start_generation(subject['id'], rubric['id'])
    print(f"Job ID: {job['job_id']}")
    
    result = poll_job(job['job_id'])
    
    if result:
        print(f"Generated {result.get('total_questions_generated')} questions.")
        print(f"Avg Confidence: {result.get('avg_confidence_score')}")

if __name__ == "__main__":
    main()
