import os
import json
import re
import uuid
import httpx
from pathlib import Path
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from jose import jwt

from app.db import get_conn, get_cursor, init_db
from app.auth import hash_password, verify_password, create_access_token, decode_token, SECRET_KEY, ALGORITHM

# Load dataset
DATASET_PATH = Path(__file__).parent.parent / "Dataset" / "data.json"
ALT_DATASET = Path(__file__).parent.parent / "dataset" / "role_skills_dataset.json"

with open(DATASET_PATH, encoding="utf-8") as f:
    RAW = json.load(f)

ROLES = RAW.get("roles", [])
SKILLS_MAP = RAW.get("skills", {})

# Build reverse alias map for fuzzy matching
ALIAS_TO_CANON = {}
CANON_SET = set(SKILLS_MAP.keys())
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

def canonical_skill(raw: str) -> Optional[str]:
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
    # exact
    for r in ROLES:
        if r["role"].lower() == role_input.lower():
            return r
        if role_input.lower() in [a.lower() for a in r.get("aliases", [])]:
            return r
    # fuzzy normalized
    norm = normalize_skill(role_input)
    for r in ROLES:
        if normalize_skill(r["role"]) == norm:
            return r
        for a in r.get("aliases", []):
            if normalize_skill(a) == norm:
                return r
    # partial
    for r in ROLES:
        if norm in normalize_skill(r["role"]) or normalize_skill(r["role"]) in norm:
            return r
    return None

app = FastAPI(title="skilly API", version="1.0.0", description="skilly - are you industry ready")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# --- Auth helpers ---
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid scheme")
    except:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("SELECT id, email, full_name FROM public.profiles WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

class SignupIn(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class SigninIn(BaseModel):
    email: str
    password: str

class AnalyzeIn(BaseModel):
    target_role: str
    skills: List[str]

class JobAnalyzeIn(BaseModel):
    target_role: Optional[str] = None
    job_description: str
    user_skills: Optional[List[str]] = None

class CompareIn(BaseModel):
    roles: List[str]
    user_skills: Optional[List[str]] = None

class RoadmapIn(BaseModel):
    target_role: str
    skills: List[str]
    days: int = 30

class ChatIn(BaseModel):
    message: str
    target_role: Optional[str] = None
    missing_skills: Optional[List[str]] = None

@app.get("/")
def root():
    return {"name": "skilly", "tagline": "are you industry ready", "version": "1.0.0", "roles": len(ROLES), "skills": len(SKILLS_MAP)}

@app.get("/api/health")
def health():
    return {"status": "ok", "db": "connected"}

# --- Auth ---
@app.post("/api/auth/signup")
def signup(data: SignupIn):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM public.profiles WHERE email = %s", (data.email.lower(),))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())
    pwd_hash = hash_password(data.password)
    cur.execute("INSERT INTO public.profiles (id, email, full_name, password_hash) VALUES (%s, %s, %s, %s)", (user_id, data.email.lower(), data.full_name, pwd_hash))
    conn.commit()
    cur.close(); conn.close()
    token = create_access_token({"sub": user_id, "email": data.email.lower()})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user_id, "email": data.email.lower(), "full_name": data.full_name}}

@app.post("/api/auth/signin")
def signin(data: SigninIn):
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("SELECT id, email, full_name, password_hash FROM public.profiles WHERE email = %s", (data.email.lower(),))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": row["id"], "email": row["email"]})
    return {"access_token": token, "token_type": "bearer", "user": {"id": row["id"], "email": row["email"], "full_name": row["full_name"]}}

@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return user

# --- Roles & Skills ---
@app.get("/api/roles")
def list_roles(q: Optional[str] = None, limit: int = 100):
    if q:
        filtered = [r for r in ROLES if q.lower() in r["role"].lower() or any(q.lower() in a.lower() for a in r.get("aliases", []))]
        return filtered[:limit]
    return ROLES[:limit]

@app.get("/api/roles/{role_name}")
def get_role(role_name: str):
    role = find_role(role_name)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@app.get("/api/skills")
def list_skills():
    return {"skills": SKILLS_MAP, "count": len(SKILLS_MAP)}

@app.get("/api/skills/canonical/{raw}")
def canonical(raw: str):
    canon = canonical_skill(raw)
    if not canon:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"input": raw, "canonical": canon, "aliases": SKILLS_MAP.get(canon, [])}

# --- Core analysis ---
def do_gap_analysis(target_role: str, user_skills_raw: List[str]):
    role = find_role(target_role)
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{target_role}' not found")
    # canonicalize user skills
    user_canonical = set()
    for s in user_skills_raw:
        c = canonical_skill(s)
        if c:
            user_canonical.add(c)
        else:
            # try normalize and keep as is if not found, for display
            user_canonical.add(normalize_skill(s))
    # also add raw lower for matching fallback
    user_norm_set = set(normalize_skill(s) for s in user_skills_raw)
    role_skills = role.get("skills", {})  # dict skill->weight
    strong = []
    partial = []
    missing = []
    for skill_key, weight in role_skills.items():
        canon = skill_key
        # check if user has it (via canonical or normalized)
        has = False
        if canon in user_canonical:
            has = True
        else:
            # check aliases
            aliases = SKILLS_MAP.get(canon, [])
            for a in aliases:
                if normalize_skill(a) in user_norm_set:
                    has = True
                    break
        if has:
            if weight >= 4:
                strong.append({"skill": canon, "weight": weight, "label": canon.replace("_"," ")})
            else:
                partial.append({"skill": canon, "weight": weight, "label": canon.replace("_"," ")})
        else:
            # missing: decide partial vs missing based on weight
            if weight <= 3:
                partial.append({"skill": canon, "weight": weight, "label": canon.replace("_"," ")})
            else:
                missing.append({"skill": canon, "weight": weight, "label": canon.replace("_"," ")})
    # For gap display, Strong = has, Missing = not has
    # Move partial that are actually missing to missing if user doesn't have? Already done.
    # But we want Strong = has, Partial = has with low weight? Already sorted.
    # Ensure missing are sorted by weight desc
    missing_sorted = sorted(missing, key=lambda x: x["weight"], reverse=True)
    partial_sorted = sorted(partial, key=lambda x: x["weight"], reverse=True)
    strong_sorted = sorted(strong, key=lambda x: x["weight"], reverse=True)
    total = len(role_skills)
    readiness = round((len(strong_sorted) / total * 100) if total else 0)
    # Priority = missing sorted
    priority = [m["skill"] for m in missing_sorted]
    # Roadmap = priority ordered
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

@app.post("/api/analyze")
def analyze(data: AnalyzeIn, user=Depends(get_current_user)):
    result = do_gap_analysis(data.target_role, data.skills)
    # save to DB
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

@app.post("/api/analyze/public")
def analyze_public(data: AnalyzeIn):
    # no auth required for demo
    return do_gap_analysis(data.target_role, data.skills)

@app.get("/api/roadmap")
def roadmap(target_role: str, skills: str = ""):
    # skills as comma separated
    user_skills = [s.strip() for s in skills.split(",") if s.strip()]
    result = do_gap_analysis(target_role, user_skills)
    return {"role": result["role"], "roadmap": result["roadmap"], "priority": result["priority"], "readiness": result["readiness"]}

@app.get("/api/graph")
def graph(target_role: str):
    role = find_role(target_role)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    skills = list(role.get("skills", {}).keys())
    # Build simple dependency graph: connect high weight skills to low weight?
    nodes = [{"id": s, "label": s.replace("_"," "), "weight": w} for s, w in role["skills"].items()]
    # edges: link each skill to next by weight proximity
    edges = []
    sorted_skills = sorted(role["skills"].items(), key=lambda x: x[1], reverse=True)
    for i in range(len(sorted_skills)-1):
        edges.append({"from": sorted_skills[i][0], "to": sorted_skills[i+1][0]})
    # also center node is role
    return {"role": role["role"], "nodes": nodes, "edges": edges}

# --- Job analyzer ---
@app.post("/api/job-analyze")
def job_analyze(data: JobAnalyzeIn):
    # extract skills from job description via alias matching
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

# --- Resume extract ---
@app.post("/api/resume-extract")
async def resume_extract(file: UploadFile = File(None), text: str = Form(None)):
    content = ""
    if file:
        data = await file.read()
        # try pdf
        try:
            from PyPDF2 import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data))
            for page in reader.pages:
                content += (page.extract_text() or "") + "\n"
        except:
            try:
                content = data.decode("utf-8", errors="ignore")
            except:
                content = ""
    if text:
        content += "\n" + text
    content_lower = content.lower()
    extracted = []
    for canon, aliases in SKILLS_MAP.items():
        for a in aliases:
            if a.lower() in content_lower:
                extracted.append(canon)
                break
    extracted = list(set(extracted))
    return {"text_preview": content[:2000], "skills": extracted, "count": len(extracted)}

# --- GitHub ---
@app.get("/api/github/{username}")
async def github_analyze(username: str):
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"https://api.github.com/users/{username}/repos", params={"per_page": 20}, headers={"User-Agent": "skilly"})
            repos = r.json() if r.status_code == 200 else []
            langs = {}
            for repo in repos[:20]:
                lang = repo.get("language")
                if lang:
                    key = lang.lower()
                    canon = canonical_skill(key)
                    if canon:
                        langs[canon] = langs.get(canon, 0) + 1
                    else:
                        langs[key] = langs.get(key, 0) + 1
            # also fetch languages for top repo
            skills = list(langs.keys())
            # map to canonical
            canonical_skills = [canonical_skill(s) or s for s in skills]
            return {"username": username, "repos_count": len(repos), "languages": langs, "skills": list(set(canonical_skills))}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# --- Compare ---
@app.post("/api/compare")
def compare(data: CompareIn):
    roles_data = []
    for rname in data.roles:
        role = find_role(rname)
        if role:
            roles_data.append(role)
    if len(roles_data) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 roles")
    # common skills
    skill_sets = [set(r["skills"].keys()) for r in roles_data]
    common = set.intersection(*skill_sets) if skill_sets else set()
    all_skills = set.union(*skill_sets) if skill_sets else set()
    # user gaps per role if provided
    per_role = []
    for r in roles_data:
        if data.user_skills is not None:
            gap = do_gap_analysis(r["role"], data.user_skills)
            per_role.append({"role": r["role"], "readiness": gap["readiness"], "missing": gap["missing"]})
        else:
            per_role.append({"role": r["role"], "skills": list(r["skills"].keys())})
    return {"common_skills": list(common), "all_skills": list(all_skills), "per_role": per_role}

# --- Roadmap timed ---
@app.post("/api/roadmap/timed")
def timed_roadmap(data: RoadmapIn):
    result = do_gap_analysis(data.target_role, data.skills)
    missing = result["missing"]
    if not missing:
        return {"roadmap": [], "message": "No gaps, you are ready"}
    days = max(1, data.days)
    per_day = max(1, len(missing) // days + (1 if len(missing) % days else 0))
    # chunk
    plan = []
    for i in range(0, len(missing), per_day):
        chunk = missing[i:i+per_day]
        plan.append({"days": f"Day {i//per_day + 1}", "skills": [c["skill"] for c in chunk]})
    return {"role": result["role"], "total_missing": len(missing), "plan": plan, "readiness": result["readiness"]}

# --- Progress ---
@app.get("/api/progress")
def progress(user=Depends(get_current_user)):
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("SELECT id, target_role, readiness_score, created_at FROM public.analyses WHERE user_id = %s ORDER BY created_at DESC LIMIT 20", (user["id"],))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return {"analyses": rows}

# --- Chat ---
@app.post("/api/chat")
def chat(data: ChatIn):
    # simple rule-based chat
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

@app.get("/api/dashboard")
def dashboard(user=Depends(get_current_user)):
    # aggregate for dashboard home
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("SELECT count(*) as c, avg(readiness_score) as avg FROM public.analyses WHERE user_id = %s", (user["id"],))
    stats = cur.fetchone()
    cur.execute("SELECT target_role, readiness_score, created_at FROM public.analyses WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user["id"],))
    latest = cur.fetchone()
    cur.close(); conn.close()
    return {"user": user, "stats": stats, "latest": latest, "roles_total": len(ROLES), "skills_total": len(SKILLS_MAP)}
