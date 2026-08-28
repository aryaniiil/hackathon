import json
from fastapi import APIRouter, Depends
from app.models import AnalyzeIn
from app.routes.auth import get_current_user
from app.utils import do_gap_analysis
from app.db import get_conn

router = APIRouter(prefix="/api", tags=["analyze"])

@router.post("/analyze")
def analyze(data: AnalyzeIn, user=Depends(get_current_user)):
    result = do_gap_analysis(data.target_role, data.skills)
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO public.analyses (user_id, target_role, readiness_score, strong_skills, partial_skills, missing_skills, roadmap) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, created_at",
                    (user["id"], result["role"], result["readiness"], json.dumps(result["strong"]), json.dumps(result["partial"]), json.dumps(result["missing"]), json.dumps(result["roadmap"])))
        row = cur.fetchone()
        conn.commit()
        cur.close(); conn.close()
        result["analysis_id"] = str(row[0])
        result["created_at"] = str(row[1])
    except Exception as e:
        print("save error", e)
    return result

@router.post("/analyze/public")
def analyze_public(data: AnalyzeIn):
    return do_gap_analysis(data.target_role, data.skills)

@router.get("/roadmap")
def roadmap(target_role: str, skills: str = ""):
    user_skills = [s.strip() for s in skills.split(",") if s.strip()]
    result = do_gap_analysis(target_role, user_skills)
    return {"role": result["role"], "roadmap": result["roadmap"], "priority": result["priority"], "readiness": result["readiness"]}

@router.get("/graph")
def graph(target_role: str):
    from app.utils import find_role
    from fastapi import HTTPException
    role = find_role(target_role)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    skills = list(role.get("skills", {}).keys())
    nodes = [{"id": s, "label": s.replace("_"," "), "weight": w} for s, w in role["skills"].items()]
    sorted_skills = sorted(role["skills"].items(), key=lambda x: x[1], reverse=True)
    edges = []
    for i in range(len(sorted_skills)-1):
        edges.append({"from": sorted_skills[i][0], "to": sorted_skills[i+1][0]})
    return {"role": role["role"], "nodes": nodes, "edges": edges}
