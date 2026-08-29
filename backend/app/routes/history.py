import uuid
import json
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.db import get_conn, get_cursor
from app.routes.auth import get_current_user
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY

router = APIRouter(prefix="/api", tags=["history"])

class HistoryIn(BaseModel):
    target_role: str
    claimed_skills: List[str]
    score: int
    total: int
    percentage: int
    level: str
    mcq_score: Optional[int] = 0
    mcq_total: Optional[int] = 12
    text_points: Optional[int] = 0
    text_max: Optional[int] = 6
    per_skill: Optional[Dict[str, Any]] = {}
    strengths: Optional[List[str]] = []
    weaknesses: Optional[List[str]] = []
    ai_summary: Optional[Dict[str, Any]] = None

@router.post("/history")
def save_history(data: HistoryIn, user=Depends(get_current_user), authorization: str = Header(None)):
    # Try direct DB first
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.test_history
            (user_id, target_role, claimed_skills, score, total, percentage, level, mcq_score, mcq_total, text_points, text_max, per_skill, strengths, weaknesses, ai_summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            user["id"],
            data.target_role,
            json.dumps(data.claimed_skills),
            data.score,
            data.total,
            data.percentage,
            data.level,
            data.mcq_score or 0,
            data.mcq_total or 12,
            data.text_points or 0,
            data.text_max or 6,
            json.dumps(data.per_skill or {}),
            json.dumps(data.strengths or []),
            json.dumps(data.weaknesses or []),
            json.dumps(data.ai_summary) if data.ai_summary else None
        ))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {"id": str(row[0]), "created_at": str(row[1]), "message": "saved"}
    except Exception as e:
        print(f"[history] DB save failed, trying REST: {e}")
        # Fallback to Supabase REST with user's token (for EC2 where direct DB unreachable)
        try:
            token = authorization.split(" ", 1)[1] if authorization and " " in authorization else ""
            if not token:
                raise HTTPException(status_code=500, detail=str(e))
            headers = {
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            payload = {
                "user_id": user["id"],
                "target_role": data.target_role,
                "claimed_skills": data.claimed_skills,
                "score": data.score,
                "total": data.total,
                "percentage": data.percentage,
                "level": data.level,
                "mcq_score": data.mcq_score or 0,
                "mcq_total": data.mcq_total or 12,
                "text_points": data.text_points or 0,
                "text_max": data.text_max or 6,
                "per_skill": data.per_skill or {},
                "strengths": data.strengths or [],
                "weaknesses": data.weaknesses or [],
                "ai_summary": data.ai_summary
            }
            r = httpx.post(f"{SUPABASE_URL}/rest/v1/test_history", headers=headers, json=payload, timeout=10)
            if r.status_code in (200,201):
                j = r.json()
                if isinstance(j, list) and j:
                    return {"id": j[0]["id"], "created_at": j[0]["created_at"], "message": "saved via REST"}
                return {"id": str(uuid.uuid4()), "created_at": "", "message": "saved via REST"}
            raise HTTPException(status_code=500, detail=f"REST failed {r.status_code}: {r.text[:200]}")
        except HTTPException:
            raise
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))

@router.get("/history")
def get_history(limit: int = 20, user=Depends(get_current_user), authorization: str = Header(None)):
    try:
        conn = get_conn()
        cur = get_cursor(conn)
        cur.execute("""
            SELECT id, target_role, claimed_skills, score, total, percentage, level,
                   mcq_score, mcq_total, text_points, text_max, per_skill, strengths, weaknesses, ai_summary, created_at
            FROM public.test_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user["id"], limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"history": rows, "count": len(rows)}
    except Exception as e:
        print(f"[history] DB fetch failed, trying REST: {e}")
        try:
            token = authorization.split(" ", 1)[1] if authorization and " " in authorization else ""
            headers = {
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}" if token else f"Bearer {SUPABASE_ANON_KEY}",
            }
            params = {"user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": str(limit), "select": "*"}
            r = httpx.get(f"{SUPABASE_URL}/rest/v1/test_history", headers=headers, params=params, timeout=10)
            if r.status_code == 200:
                rows = r.json()
                return {"history": rows, "count": len(rows)}
            return {"history": [], "count": 0}
        except Exception as e2:
            print(f"[history] REST fetch failed: {e2}")
            return {"history": [], "count": 0}

@router.get("/history/{history_id}")
def get_history_one(history_id: str, user=Depends(get_current_user)):
    conn = get_conn()
    cur = get_cursor(conn)
    cur.execute("""
        SELECT id, target_role, claimed_skills, score, total, percentage, level,
               mcq_score, mcq_total, text_points, text_max, per_skill, strengths, weaknesses, ai_summary, created_at
        FROM public.test_history
        WHERE id = %s AND user_id = %s
    """, (history_id, user["id"]))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row
