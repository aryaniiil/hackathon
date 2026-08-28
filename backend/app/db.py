import os
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set - configure .env")
    return psycopg2.connect(DATABASE_URL)

def get_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)

def init_db():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.profiles (
                id UUID PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT,
                password_hash TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                is_verified BOOLEAN DEFAULT FALSE
            );
        """)
        # add column if missing for existing db
        cur.execute("ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.analyses (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
                target_role TEXT NOT NULL,
                readiness_score INT,
                strong_skills JSONB DEFAULT '[]'::jsonb,
                partial_skills JSONB DEFAULT '[]'::jsonb,
                missing_skills JSONB DEFAULT '[]'::jsonb,
                roadmap JSONB DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.user_skills (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
                skill_key TEXT NOT NULL,
                skill_label TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.otp_codes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                verified BOOLEAN DEFAULT FALSE,
                attempts INT DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_otp_email ON public.otp_codes(email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_otp_expires ON public.otp_codes(expires_at);")
        # Test history table - proper DB storage, not localStorage
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.test_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
                target_role TEXT NOT NULL,
                claimed_skills JSONB DEFAULT '[]'::jsonb,
                score INT NOT NULL,
                total INT NOT NULL,
                percentage INT NOT NULL,
                level TEXT NOT NULL,
                mcq_score INT DEFAULT 0,
                mcq_total INT DEFAULT 12,
                text_points INT DEFAULT 0,
                text_max INT DEFAULT 6,
                per_skill JSONB DEFAULT '{}'::jsonb,
                strengths JSONB DEFAULT '[]'::jsonb,
                weaknesses JSONB DEFAULT '[]'::jsonb,
                ai_summary JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_test_history_user ON public.test_history(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_test_history_created ON public.test_history(created_at DESC);")
        # Also ensure analyses table has user_id index
        cur.execute("CREATE INDEX IF NOT EXISTS idx_analyses_user ON public.analyses(user_id);")
        conn.commit()
        cur.close()
        conn.close()
        print("[db] init ok")
    except Exception as e:
        print(f"[db] init skipped/failed: {e}")
        try:
            conn.close()
        except:
            pass
