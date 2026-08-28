from fastapi import APIRouter
from app.models import JobAnalyzeIn
from app.config import SKILLS_MAP
from app.utils import do_gap_analysis

router = APIRouter(prefix="/api", tags=["job"])

@router.post("/job-analyze")
def job_analyze(data: JobAnalyzeIn):
    text = data.job_description.lower()
    found = []
    for canon, aliases in SKILLS_MAP.items():
        for a in aliases:
            if a.lower() in text:
                found.append(canon)
                break
        else:
            if canon.replace("_"," ") in text:
                found.append(canon)
    found = list(set(found))
    result = None
    if data.target_role:
        result = do_gap_analysis(data.target_role, data.user_skills or [])
        job_missing = [s for s in found if s not in result["user_skills_canonical"]]
        return {"job_skills": found, "analysis": result, "job_missing": job_missing}
    return {"job_skills": found}
