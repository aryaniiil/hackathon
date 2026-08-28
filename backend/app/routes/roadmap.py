from fastapi import APIRouter
from app.models import RoadmapIn, CompareIn
from app.utils import do_gap_analysis, find_role
from fastapi import HTTPException

router = APIRouter(prefix="/api", tags=["roadmap"])

@router.post("/roadmap/timed")
def timed_roadmap(data: RoadmapIn):
    result = do_gap_analysis(data.target_role, data.skills)
    missing = result["missing"]
    if not missing:
        return {"roadmap": [], "message": "No gaps, you are ready"}
    days = max(1, data.days)
    per_day = max(1, len(missing) // days + (1 if len(missing) % days else 0))
    plan = []
    for i in range(0, len(missing), per_day):
        chunk = missing[i:i+per_day]
        plan.append({"days": f"Day {i//per_day + 1}", "skills": [c["skill"] for c in chunk]})
    return {"role": result["role"], "total_missing": len(missing), "plan": plan, "readiness": result["readiness"]}

@router.post("/compare")
def compare(data: CompareIn):
    from app.config import ROLES
    roles_data = []
    for rname in data.roles:
        role = find_role(rname)
        if role:
            roles_data.append(role)
    if len(roles_data) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 roles")
    skill_sets = [set(r["skills"].keys()) for r in roles_data]
    common = set.intersection(*skill_sets) if skill_sets else set()
    all_skills = set.union(*skill_sets) if skill_sets else set()
    per_role = []
    for r in roles_data:
        if data.user_skills is not None:
            gap = do_gap_analysis(r["role"], data.user_skills)
            per_role.append({"role": r["role"], "readiness": gap["readiness"], "missing": gap["missing"]})
        else:
            per_role.append({"role": r["role"], "skills": list(r["skills"].keys())})
    return {"common_skills": list(common), "all_skills": list(all_skills), "per_role": per_role}
