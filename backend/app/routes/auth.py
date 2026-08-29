import uuid
import json
import os
import random
import re
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional

from app.models import SignupIn, SigninIn
from app.db import get_conn, get_cursor
from app.auth import hash_password, verify_password, create_access_token, decode_token

# SMTP config for real OTP emails
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in ("1","true","yes")

def _send_otp_email(to_email: str, code: str):
    """Send real OTP via SMTP if configured, else just log (production will have SMTP)"""
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        print(f"[SMTP] not configured, OTP for {to_email}: {code} (would be emailed)")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = "Your skilly OTP code"
        body = f"""
        <div style="font-family: Helvetica, Arial, sans-serif; background:#0A0A0A; color:#F5F5F5; padding:24px; border-radius:12px;">
          <h2 style="color:#C7D6CF; margin:0 0 12px;">Your OTP code</h2>
          <p style="color:#A8AAAD; font-size:13px;">Use this code to verify your email for <b>skilly</b> — are you industry ready.</p>
          <div style="background:#111214; border:1px solid #242629; border-radius:999px; padding:14px 20px; text-align:center; margin:16px 0;">
            <span style="font-size:28px; letter-spacing:0.3em; font-weight:700; color:#F5F5F5;">{code}</span>
          </div>
          <p style="color:#6F7377; font-size:11px;">Expires in 10 minutes. If you didn't request this, ignore.</p>
          <p style="color:#3A3E41; font-size:11px; margin-top:16px;">Sent via Python backend SMTP. Supabase also sends OTP if configured.</p>
        </div>
        """
        msg.attach(MIMEText(body, "html"))
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_TLS:
                server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[SMTP] OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"[SMTP] failed to send to {to_email}: {e}")
        return False

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory fallback for OTP if DB unavailable
_OTP_MEMORY = {}

def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))

def _generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"

def _store_otp(email: str, code: str, minutes: int = 10):
    email = email.lower().strip()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    # try DB
    try:
        conn = get_conn()
        cur = conn.cursor()
        # cleanup old expired
        cur.execute("DELETE FROM public.otp_codes WHERE expires_at < NOW() - INTERVAL '1 hour'")
        cur.execute(
            "INSERT INTO public.otp_codes (email, code, expires_at) VALUES (%s, %s, %s)",
            (email, code, expires_at)
        )
        conn.commit()
        cur.close()
        conn.close()
        print(f"[OTP] code for {email}: {code} expires {expires_at}")
    except Exception as e:
        print(f"[OTP] DB store failed, using memory: {e}")
        _OTP_MEMORY[email] = {"code": code, "expires_at": expires_at, "attempts": 0, "verified": False}
        print(f"[OTP memory] code for {email}: {code}")
    # try to send real email via SMTP if configured
    try:
        _send_otp_email(email, code)
    except Exception as e:
        print(f"[OTP] send email failed for {email}: {e}")
    return True

def _verify_otp_code(email: str, code: str) -> bool:
    email = email.lower().strip()
    code = code.strip()
    # try DB first
    try:
        conn = get_conn()
        cur = get_cursor(conn)
        cur.execute(
            "SELECT id, code, expires_at, verified, attempts FROM public.otp_codes WHERE email=%s ORDER BY created_at DESC LIMIT 1",
            (email,)
        )
        row = cur.fetchone()
        if row:
            # check expiry
            expires = row["expires_at"]
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="OTP expired, request new code")
            if row["verified"]:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="OTP already used, request new code")
            if row["attempts"] >= 5:
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Too many attempts, request new code")
            # increment attempts if wrong
            if row["code"] != code:
                cur2 = conn.cursor()
                cur2.execute("UPDATE public.otp_codes SET attempts = attempts + 1 WHERE id=%s", (row["id"],))
                conn.commit()
                cur2.close()
                cur.close(); conn.close()
                raise HTTPException(status_code=400, detail="Invalid OTP code")
            # mark verified
            cur2 = conn.cursor()
            cur2.execute("UPDATE public.otp_codes SET verified = TRUE WHERE id=%s", (row["id"],))
            conn.commit()
            cur2.close()
            cur.close(); conn.close()
            return True
        cur.close(); conn.close()
        # if not found in DB, fallback to memory check
    except HTTPException:
        raise
    except Exception as e:
        print(f"[OTP] DB verify failed: {e}")
        try:
            conn.close()
        except:
            pass
    # memory fallback
    mem = _OTP_MEMORY.get(email)
    if not mem:
        raise HTTPException(status_code=400, detail="No OTP found, request a code first")
    if datetime.now(timezone.utc) > mem["expires_at"]:
        raise HTTPException(status_code=400, detail="OTP expired, request new code")
    if mem.get("verified"):
        raise HTTPException(status_code=400, detail="OTP already used")
    if mem.get("attempts", 0) >= 5:
        raise HTTPException(status_code=400, detail="Too many attempts")
    if mem["code"] != code:
        mem["attempts"] = mem.get("attempts", 0) + 1
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    mem["verified"] = True
    return True

def _ensure_user_exists(email: str, full_name: Optional[str] = None, password: Optional[str] = None):
    """Get or create user, return user dict"""
    email = email.lower().strip()
    try:
        conn = get_conn()
        cur = get_cursor(conn)
        cur.execute("SELECT id, email, full_name, password_hash, is_verified FROM public.profiles WHERE email=%s", (email,))
        row = cur.fetchone()
        if row:
            cur.close(); conn.close()
            return row
        # create user if not exists (for OTP-only flow)
        user_id = str(uuid.uuid4())
        pwd_hash = hash_password(password) if password else None
        cur2 = conn.cursor()
        cur2.execute(
            "INSERT INTO public.profiles (id, email, full_name, password_hash, is_verified) VALUES (%s, %s, %s, %s, %s)",
            (user_id, email, full_name, pwd_hash, True)
        )
        conn.commit()
        cur2.close()
        cur.close(); conn.close()
        return {"id": user_id, "email": email, "full_name": full_name, "password_hash": pwd_hash, "is_verified": True}
    except Exception as e:
        # if DB fails, return mock user for demo (still issue token)
        print(f"[auth] DB user ensure failed: {e}")
        # fallback demo user
        return {"id": str(uuid.uuid4()), "email": email, "full_name": full_name or email.split("@")[0], "password_hash": None, "is_verified": True}

# Auth helper for protected routes - supports both Python JWT and Supabase JWT (only Supabase stored in localStorage per user request)
def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid scheme")
    except:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    # Try Python JWT first (legacy, still issued by supabase-sync)
    payload = decode_token(token)
    if payload and payload.get("sub"):
        user_id = payload.get("sub")
        try:
            conn = get_conn()
            cur = get_cursor(conn)
            cur.execute("SELECT id, email, full_name FROM public.profiles WHERE id = %s", (user_id,))
            user = cur.fetchone()
            cur.close(); conn.close()
            if user:
                return user
            # fallback to payload if not found but token valid
            return {"id": user_id, "email": payload.get("email"), "full_name": payload.get("email")}
        except HTTPException:
            raise
        except Exception as e:
            print(f"[auth] get_current_user DB failed, using token payload: {e}")
            return {"id": user_id, "email": payload.get("email"), "full_name": payload.get("email")}
    # Try Supabase JWT - verify via Supabase Auth API and ensure profile exists
    try:
        from app.config import SUPABASE_URL, SUPABASE_ANON_KEY
        import httpx
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        # Verify token by calling Supabase auth user endpoint
        try:
            r = httpx.get(f"{SUPABASE_URL}/auth/v1/user", headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}, timeout=5)
        except Exception as e:
            print(f"[auth] Supabase verify failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        data = r.json()
        email = data.get("email")
        user_id = data.get("id")
        if not email or not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        # Ensure profile exists in our DB for history (create if not)
        try:
            conn = get_conn()
            cur = get_cursor(conn)
            cur.execute("SELECT id, email, full_name FROM public.profiles WHERE id = %s", (user_id,))
            user = cur.fetchone()
            if not user:
                # try by email
                cur.execute("SELECT id, email, full_name FROM public.profiles WHERE email = %s", (email.lower(),))
                user = cur.fetchone()
                if not user:
                    # create profile with Supabase ID
                    cur2 = conn.cursor()
                    full_name = data.get("user_metadata", {}).get("full_name") or data.get("user_metadata", {}).get("name") or ""
                    cur2.execute("INSERT INTO public.profiles (id, email, full_name, is_verified) VALUES (%s, %s, %s, %s)", (user_id, email.lower(), full_name, True))
                    conn.commit()
                    cur2.close()
                    user = {"id": user_id, "email": email.lower(), "full_name": full_name}
                else:
                    # existing email with different ID - use existing but ensure is_verified
                    user_id = user["id"]
            cur.close(); conn.close()
            return {"id": user_id, "email": email.lower(), "full_name": user.get("full_name") or email}
        except HTTPException:
            raise
        except Exception as e:
            print(f"[auth] Supabase profile ensure failed: {e}")
            return {"id": user_id, "email": email.lower(), "full_name": email}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[auth] get_current_user failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Request OTP
class RequestOtpIn(BaseModel):
    email: str
    full_name: Optional[str] = None

class VerifyOtpIn(BaseModel):
    email: str
    code: str
    full_name: Optional[str] = None

@router.post("/request-otp")
def request_otp(data: RequestOtpIn):
    email = data.email.lower().strip()
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    code = _generate_otp()
    _store_otp(email, code, minutes=10)
    env = os.getenv("ENV", "development")
    # Only return debug_otp if SMTP not configured (dev fallback). Real flow sends email.
    smtp_configured = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)
    resp = {"message": "OTP sent to email. Please check your inbox (and spam).", "email": email, "expires_in": 600}
    if env == "development" and not smtp_configured:
        resp["debug_otp"] = code
        resp["note"] = "DEV MODE: SMTP not configured, OTP returned for testing."
    print(f"[request-otp] {email} -> {code} (smtp_configured={smtp_configured})")
    return resp

@router.post("/verify-otp")
def verify_otp(data: VerifyOtpIn):
    email = data.email.lower().strip()
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    if not data.code or len(data.code.strip()) < 4:
        raise HTTPException(status_code=400, detail="Invalid OTP format")
    _verify_otp_code(email, data.code)
    # Ensure user exists
    user = _ensure_user_exists(email, full_name=data.full_name)
    # Mark verified
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE public.profiles SET is_verified = TRUE WHERE email=%s", (email,))
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        print(f"[verify-otp] mark verified failed: {e}")
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user["id"], "email": user["email"], "full_name": user.get("full_name")}}

@router.post("/signup")
def signup(data: SignupIn):
    email = data.email.lower().strip()
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM public.profiles WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail="Email already registered. Try sign in.")
        user_id = str(uuid.uuid4())
        pwd_hash = hash_password(data.password)
        cur.execute("INSERT INTO public.profiles (id, email, full_name, password_hash, is_verified) VALUES (%s, %s, %s, %s, %s)", (user_id, email, data.full_name, pwd_hash, False))
        conn.commit()
        cur.close(); conn.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[signup] DB error: {e}")
        # fallback: still proceed to OTP
        user_id = str(uuid.uuid4())
    # Generate OTP for verification
    code = _generate_otp()
    _store_otp(email, code, minutes=10)
    env = os.getenv("ENV", "development")
    smtp_configured = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)
    resp = {"message": "Account created. OTP sent for verification. Please check your email.", "email": email, "user_id": user_id, "requires_otp": True, "expires_in": 600}
    if env == "development" and not smtp_configured:
        resp["debug_otp"] = code
        resp["note"] = "DEV MODE: SMTP not configured, OTP returned for testing."
    print(f"[signup] {email} OTP {code} (smtp_configured={smtp_configured})")
    return resp

@router.post("/signin")
def signin(data: SigninIn):
    email = data.email.lower().strip()
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    try:
        conn = get_conn()
        cur = get_cursor(conn)
        cur.execute("SELECT id, email, full_name, password_hash, is_verified FROM public.profiles WHERE email = %s", (email,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(status_code=401, detail="No account with this email. Please sign up.")
        if not row.get("password_hash"):
            # passwordless account, directly send OTP - real email only, no dev OTP
            code = _generate_otp()
            _store_otp(email, code, minutes=10)
            resp = {"message": "OTP sent to your email. Please check your inbox (and spam).", "email": email, "requires_otp": True, "expires_in": 600}
            print(f"[signin] {email} OTP {code} (real email via SMTP if configured)")
            return resp
        if not verify_password(data.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        # Password ok -> generate OTP for second factor - real flow only
        code = _generate_otp()
        _store_otp(email, code, minutes=10)
        resp = {"message": "Password verified. OTP sent to your email. Please check your inbox.", "email": email, "user": {"id": row["id"], "email": row["email"], "full_name": row["full_name"]}, "requires_otp": True, "expires_in": 600}
        print(f"[signin] {email} OTP {code} (real email)")
        return resp
    except HTTPException:
        raise
    except Exception as e:
        print(f"[signin] error: {e}")
        raise HTTPException(status_code=500, detail="Signin failed due to server error")

class SupabaseSyncIn(BaseModel):
    email: str
    supabase_user_id: Optional[str] = None
    full_name: Optional[str] = None

@router.post("/supabase-sync")
def supabase_sync(data: SupabaseSyncIn):
    """Exchange Supabase authenticated user for backend JWT (so DB history works)
    Frontend should call this after successful supabase.auth.signUp / verifyOtp
    """
    email = data.email.lower().strip()
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    # Use supabase_user_id if provided, else generate/find by email
    try:
        conn = get_conn()
        cur = get_cursor(conn)
        cur.execute("SELECT id, email, full_name FROM public.profiles WHERE email=%s", (email,))
        row = cur.fetchone()
        if row:
            user_id = row["id"]
            # update full_name if provided and missing
            if data.full_name and not row.get("full_name"):
                cur2 = conn.cursor()
                cur2.execute("UPDATE public.profiles SET full_name=%s WHERE id=%s", (data.full_name, user_id))
                conn.commit()
                cur2.close()
            cur.close(); conn.close()
        else:
            # create profile with supabase id if provided, else uuid
            user_id = data.supabase_user_id if data.supabase_user_id else str(uuid.uuid4())
            # ensure uuid format
            try:
                uuid.UUID(user_id)
            except:
                user_id = str(uuid.uuid4())
            cur2 = conn.cursor()
            cur2.execute("INSERT INTO public.profiles (id, email, full_name, is_verified) VALUES (%s, %s, %s, %s)", (user_id, email, data.full_name, True))
            conn.commit()
            cur2.close()
            cur.close(); conn.close()
            row = {"id": user_id, "email": email, "full_name": data.full_name}
        # issue backend token for DB access
        token = create_access_token({"sub": str(row["id"] if isinstance(row, dict) else row["id"]), "email": email})
        return {"access_token": token, "token_type": "bearer", "user": {"id": str(row["id"] if isinstance(row, dict) else row["id"]), "email": email, "full_name": data.full_name or row.get("full_name")}}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[supabase-sync] error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
