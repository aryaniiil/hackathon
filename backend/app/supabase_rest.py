import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or SUPABASE_ANON_KEY

def _headers(use_service=False):
    key = SUPABASE_SERVICE_KEY if use_service and SUPABASE_SERVICE_KEY else SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def rest_get(table, params=None, limit=20, use_service=False):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params is None:
        params = {}
    params["limit"] = limit
    try:
        r = httpx.get(url, headers=_headers(use_service), params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        print(f"[rest_get] {table} failed {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"[rest_get] error {e}")
        return None

def rest_post(table, data, use_service=False):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        r = httpx.post(url, headers=_headers(use_service), json=data, timeout=10)
        if r.status_code in (200, 201):
            return r.json()
        print(f"[rest_post] {table} failed {r.status_code}: {r.text[:500]}")
        return None
    except Exception as e:
        print(f"[rest_post] error {e}")
        return None

def rest_get_user(token):
    """Verify Supabase JWT via auth user endpoint"""
    try:
        r = httpx.get(f"{SUPABASE_URL}/auth/v1/user", headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}, timeout=5)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None
