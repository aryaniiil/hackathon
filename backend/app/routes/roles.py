from fastapi import APIRouter, HTTPException
from typing import Optional
from app.config import ROLES, SKILLS_MAP
from app.utils import find_role, canonical_skill

router = APIRouter(prefix="/api", tags=["roles"])

@router.get("/roles")
def list_roles(q: Optional[str] = None, limit: int = 100):
    if q:
        filtered = [r for r in ROLES if q.lower() in r["role"].lower() or any(q.lower() in a.lower() for a in r.get("aliases", []))]
        return filtered[:limit]
    return ROLES[:limit]

@router.get("/roles/{role_name}")
def get_role(role_name: str):
    role = find_role(role_name)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.get("/skills")
def list_skills():
    return {"skills": SKILLS_MAP, "count": len(SKILLS_MAP)}

@router.get("/skills/canonical/{raw}")
def canonical(raw: str):
    canon = canonical_skill(raw)
    if not canon:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"input": raw, "canonical": canon, "aliases": SKILLS_MAP.get(canon, [])}
