import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.db import get_conn, get_cursor
from app.routes.auth import get_current_user

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
def save_history(data: HistoryIn, user=Depends(get_current_user)):
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_history(limit: int = 20, user=Depends(get_current_user)):
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
