import json
from database import SessionLocal
from models import VettedQuestion, GeneratedQuestion, Subject

db = SessionLocal()
data = {
    "vetted_count": 0,
    "pending_count": 0,
    "vetted_list": []
}

try:
    vetted = db.query(VettedQuestion).all()
    data["vetted_count"] = len(vetted)
    for v in vetted:
        data["vetted_list"].append({
            "id": v.id,
            "subject_id": v.subject_id,
            "verdict": v.verdict,
            "text_snippet": v.question_text[:30] if v.question_text else ""
        })

    pending = db.query(GeneratedQuestion).filter(GeneratedQuestion.status == 'pending').count()
    data["pending_count"] = pending

    print(json.dumps(data, indent=2))

finally:
    db.close()
