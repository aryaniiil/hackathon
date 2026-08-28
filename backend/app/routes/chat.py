from fastapi import APIRouter
from app.models import ChatIn

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat")
def chat(data: ChatIn):
    msg = data.message.lower()
    if "roadmap" in msg or "learn" in msg:
        if data.missing_skills:
            return {"reply": f"Start with {', '.join(data.missing_skills[:3])}. These are highest priority for {data.target_role or 'your role'}. Focus 1-2 weeks per skill with hands-on projects."}
        return {"reply": "Pick a target role first, then I can build your roadmap."}
    if "ready" in msg or "score" in msg:
        return {"reply": "Your readiness is based on matched skills vs role weight. Add more high-weight skills like Python, System Design to boost quickly."}
    if "gap" in msg:
        return {"reply": f"Your gaps are {', '.join(data.missing_skills[:5]) if data.missing_skills else 'not yet analyzed'}. Want a 30-day plan?"}
    return {"reply": f"You asked: '{data.message}'. For {data.target_role or 'your role'}, focus on closing gaps in order of weight. Need a timed roadmap?"}
