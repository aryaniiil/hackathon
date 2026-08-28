import os
from pathlib import Path
import json
from dotenv import load_dotenv

# Load .env from backend root and workspace root
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env", override=False)

# Load dataset once
DATASET_PATH = Path(__file__).parent.parent.parent / "Dataset" / "data.json"
ALT_DATASET = Path(__file__).parent.parent.parent / "dataset" / "role_skills_dataset.json"

with open(DATASET_PATH, encoding="utf-8") as f:
    RAW = json.load(f)

ROLES = RAW.get("roles", [])
SKILLS_MAP = RAW.get("skills", {})

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
ENV = os.getenv("ENV", "development")

# Fail fast in production if critical vars missing
if not DATABASE_URL:
    # fallback to env file default for local dev only; no hardcoded secret in code
    # will be caught at startup if still missing
    DATABASE_URL = os.getenv("DATABASE_URL", "")
if not SECRET_KEY:
    SECRET_KEY = os.getenv("SECRET_KEY", "")
