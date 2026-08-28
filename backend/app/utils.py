import re
import json
from pathlib import Path

# Loaded from config to avoid circular import
from app.config import ROLES, SKILLS_MAP

ALIAS_TO_CANON = {}
for canon, aliases in SKILLS_MAP.items():
    for a in aliases:
        norm = re.sub(r'[^a-z0-9]', '', a.lower())
        ALIAS_TO_CANON[norm] = canon
        ALIAS_TO_CANON[a.lower()] = canon
    ALIAS_TO_CANON[canon] = canon
    ALIAS_TO_CANON[canon.lower()] = canon
    ALIAS_TO_CANON[re.sub(r'[^a-z0-9]', '', canon.lower())] = canon

def normalize_skill(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower().strip())

def canonical_skill(raw: str):
    if not raw:
        return None
    key = normalize_skill(raw)
    if key in ALIAS_TO_CANON:
        return ALIAS_TO_CANON[key]
    low = raw.lower().strip()
    if low in ALIAS_TO_CANON:
        return ALIAS_TO_CANON[low]
    return None

def find_role(role_input: str):
    if not role_input:
        return None
    for r in ROLES:
        if r["role"].lower() == role_input.lower():
            return r
        if role_input.lower() in [a.lower() for a in r.get("aliases", [])]:
            return r
    norm = normalize_skill(role_input)
    for r in ROLES:
        if normalize_skill(r["role"]) == norm:
            return r
        for a in r.get("aliases", []):
            if normalize_skill(a) == norm:
                return r
    for r in ROLES:
        if norm in normalize_skill(r["role"]) or normalize_skill(r["role"]) in norm:
            return r
    return None

def do_gap_analysis(target_role: str, user_skills_raw):
    from fastapi import HTTPException
    role = find_role(target_role)
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{target_role}' not found")
    user_canonical = set()
    for s in user_skills_raw:
        c = canonical_skill(s)
        if c:
            user_canonical.add(c)
        else:
            user_canonical.add(normalize_skill(s))
    user_norm_set = set(normalize_skill(s) for s in user_skills_raw)
    role_skills = role.get("skills", {})
    strong, partial, missing = [], [], []
    for skill_key, weight in role_skills.items():
        has = False
        if skill_key in user_canonical:
            has = True
        else:
            aliases = SKILLS_MAP.get(skill_key, [])
            for a in aliases:
                if normalize_skill(a) in user_norm_set:
                    has = True
                    break
        if has:
            if weight >= 4:
                strong.append({"skill": skill_key, "weight": weight, "label": skill_key.replace("_"," ")})
            else:
                partial.append({"skill": skill_key, "weight": weight, "label": skill_key.replace("_"," ")})
        else:
            if weight <= 3:
                partial.append({"skill": skill_key, "weight": weight, "label": skill_key.replace("_"," ")})
            else:
                missing.append({"skill": skill_key, "weight": weight, "label": skill_key.replace("_"," ")})
    missing_sorted = sorted(missing, key=lambda x: x["weight"], reverse=True)
    partial_sorted = sorted(partial, key=lambda x: x["weight"], reverse=True)
    strong_sorted = sorted(strong, key=lambda x: x["weight"], reverse=True)
    total = len(role_skills)
    readiness = round((len(strong_sorted) / total * 100) if total else 0)
    priority = [m["skill"] for m in missing_sorted]
    roadmap = priority
    return {
        "role": role["role"],
        "aliases": role.get("aliases", []),
        "readiness": readiness,
        "total_skills": total,
        "strong": strong_sorted,
        "partial": partial_sorted,
        "missing": missing_sorted,
        "priority": priority,
        "roadmap": roadmap,
        "user_skills_canonical": list(user_canonical)
    }
