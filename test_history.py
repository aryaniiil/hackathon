import sys
sys.path.insert(0, r"D:\Hackathon\backend")
from fastapi.testclient import TestClient
from main import app
import random
client = TestClient(app)
email = f"hist{random.randint(10000,99999)}@example.com"
print("email", email)
r = client.post("/api/auth/signup", json={"email": email, "password": "test1234", "full_name": "Hist User"})
print("signup", r.status_code, r.json())
otp = r.json().get("debug_otp")
r2 = client.post("/api/auth/verify-otp", json={"email": email, "code": otp})
print("verify", r2.status_code, r2.json())
token = r2.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
# generate test and evaluate
r3 = client.post("/api/skill-test/generate", json={"skills": ["python","react"], "target_role": "Frontend Developer"})
qs = r3.json()["questions"]
answers = [q["correct_index"] if q["type"]=="mcq" else "I would use reasoning because trade off handling is important for this scenario with steps." for q in qs]
r4 = client.post("/api/skill-test/evaluate", json={"questions": qs, "answers": answers, "skills": ["python","react"], "target_role": "Frontend Developer"})
eval_res = r4.json()
print("eval", eval_res["score"], eval_res["total"], eval_res["percentage"])
# get ai summary
r5 = client.post("/api/skill-test/ai-summary", json={"target_role": "Frontend Developer", "claimed_skills": ["python","react"], "test_result": eval_res, "answers_detail": [{"skill": q["skill"], "type": q["type"], "question": q["question"], "answer": answers[i]} for i,q in enumerate(qs)]})
ai = r5.json()
print("ai", ai["summary"][:100])
# save history
r6 = client.post("/api/history", json={
    "target_role": "Frontend Developer",
    "claimed_skills": ["python","react"],
    "score": eval_res["score"],
    "total": eval_res["total"],
    "percentage": eval_res["percentage"],
    "level": eval_res["level"],
    "mcq_score": eval_res["mcq_score"],
    "mcq_total": eval_res["mcq_total"],
    "text_points": eval_res["text_points"],
    "text_max": eval_res["text_max"],
    "per_skill": eval_res["per_skill"],
    "strengths": eval_res["strengths"],
    "weaknesses": eval_res["weaknesses"],
    "ai_summary": ai
}, headers=headers)
print("save history", r6.status_code, r6.json())
r7 = client.get("/api/history", headers=headers)
print("get history", r7.status_code, r7.json()["count"])
print(r7.json()["history"][0]["target_role"], r7.json()["history"][0]["percentage"])
# test supabase sync
r8 = client.post("/api/auth/supabase-sync", json={"email": email, "supabase_user_id": "00000000-0000-0000-0000-000000000000", "full_name": "Hist User"})
print("supabase sync", r8.status_code, r8.json())
