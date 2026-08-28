from fastapi import APIRouter, Depends
from app.routes.auth import get_current_user
from app.db import get_conn, get_cursor

router = APIRouter(prefix="/api", tags=["progress"])

@router.get("/progress")
def progress(user=Depends(get_current_user)):
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("SELECT id, target_role, readiness_score, created_at FROM public.analyses WHERE user_id = %s ORDER BY created_at DESC LIMIT 20", (user["id"],))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return {"analyses": rows}

@router.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    from app.config import ROLES, SKILLS_MAP
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("SELECT count(*) as c, avg(readiness_score) as avg FROM public.analyses WHERE user_id = %s", (user["id"],))
    stats = cur.fetchone()
    cur.execute("SELECT target_role, readiness_score, created_at FROM public.analyses WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user["id"],))
    latest = cur.fetchone()
    cur.close(); conn.close()
    return {"user": user, "stats": stats, "latest": latest, "roles_total": len(ROLES), "skills_total": len(SKILLS_MAP)}
