import os
import sys
from pathlib import Path
# Ensure `app` is importable whether running as `main:app` (from backend/) or `backend.main:app` (from project root)
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env")
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
try:
    from app.db import init_db
    from app.routes import auth, roles, analyze, job, resume, github, roadmap, progress, chat, skill_test, history
except ModuleNotFoundError:
    # fallback when imported as backend.main
    from backend.app.db import init_db
    from backend.app.routes import auth, roles, analyze, job, resume, github, roadmap, progress, chat, skill_test, history

app = FastAPI(
    title="skilly API",
    version="2.0.0",
    description="skilly - are you industry ready | Python FastAPI backend"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# init DB on startup
@app.on_event("startup")
def startup():
    init_db()

# include routers
app.include_router(auth.router)
app.include_router(roles.router)
app.include_router(analyze.router)
app.include_router(job.router)
app.include_router(resume.router)
app.include_router(github.router)
app.include_router(roadmap.router)
app.include_router(progress.router)
app.include_router(chat.router)
app.include_router(skill_test.router)
app.include_router(history.router)

@app.get("/")
def root():
    try:
        from app.config import ROLES, SKILLS_MAP
    except ModuleNotFoundError:
        from backend.app.config import ROLES, SKILLS_MAP
    return {"name": "skilly", "tagline": "are you industry ready", "version": "2.0.0", "roles": len(ROLES), "skills": len(SKILLS_MAP)}

@app.get("/api/health")
def health():
    # check db connectivity
    db_status = "connected"
    try:
        try:
            from app.db import get_conn
        except ModuleNotFoundError:
            from backend.app.db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"
    return {"status": "ok", "db": db_status, "backend": "FastAPI modular"}

@app.get("/api/config")
def get_config():
    """Public config for frontend - supabase anon is safe to expose, secrets never"""
    return {
        "api_version": "2.0.0",
        "env": os.getenv("ENV", "development"),
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
        "features": {
            "otp_required": True,
            "ai_enabled": bool(os.getenv("GEMINI_API_KEY")),
            "supabase_auth": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY")),
        }
    }

# Serve frontend static files if present (for single-origin deployment)
try:
    # backend/main.py -> parent is backend, parent.parent is project root -> /Website
    www_path = Path(__file__).parent.parent / "Website"
    if not www_path.exists():
        # fallback when run as backend.main from root (extra parent)
        www_path = Path(__file__).parent.parent.parent / "Website"
    if www_path.exists():
        app.mount("/app", StaticFiles(directory=str(www_path), html=True), name="frontend")
        print(f"[static] mounted Website at {www_path} -> /app")
except Exception as e:
    print(f"[static] not mounted: {e}")
