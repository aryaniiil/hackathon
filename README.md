# skilly — are you industry ready

> **Premium career intelligence platform** — pick a target role, select your skills, take an AI-generated test (12 MCQ + 3 written reasoning), get your **AI Current State** synthesized from role requirements + your claimed skills + test performance.

**Live:** `https://github.com/aryaniiil/hackathon` · **Stack:** FastAPI (Python) · Supabase Postgres + Auth · Gemini AI · Vanilla JS (premium dark SaaS)

---

## ✨ What changed (major update)

**Old flow:** complex dashboard with 10 cards (Target Role, Skills textarea, Gap Analysis, Priority, Roadmap, Graph, Job Analyzer, Compare, Chat, Progress).

**New flow (simple & human):**

```
Role (2×4 grid, search 160 roles) 
  → Skills (2×4 grid, search 216 skills + custom text, alias-aware: ml/py/reactjs) 
  → Test 15 Q (12 MCQ 4e/4m/4h + 3 ✍️ written 2-3 sentences, 5-min timer) 
  → Evaluate (MCQ 1pt + written 0-2pts scored by Gemini, 18pts total) 
  → AI Current State (Gemini fed with role-required skills + your claimed + test results + reasoning) 
  → Dashboard (single AI card) + History + Pricing + Account
```

- **Human-friendly results:** no more `MCQ -/12 • Text 0/6`; now `63% (11/18) • Intermediate • MCQ 9/12 • Written 2/6` with per-skill mastery bars and written feedback `2/2 Great reasoning`.
- **Written reasoning is mandatory & visible:** separate `SECTION 2 — Written Reasoning` with 90px textarea, word counter, `filled` state.
- **Dashboard simplified:** single AI card (`Your Current State` with summary, what you have/lack, strengths/gaps, recommendation, next steps) instead of 10 cards. Nav now `Dashboard | History | Pricing | Account`.
- **History in proper DB:** `public.test_history` in Supabase Postgres via Python, not `localStorage`. `POST /api/history` + `GET /api/history` (auth). Local cache kept only for demo fallback.
- **Search icon untouched:** preserved your fixed SVG (`left:14px; width:22px; background: rgba(199,214,207,0.06); border-radius:50%`).
- **Auth: Supabase properly + Python OTP:** `Website/js/supabase.js` now fetches `supabase_url`/`anon` from `GET /api/config` (no hardcoded secrets). `get-started.html`/`signin.html` use `supabase.auth.signUp`/`signInWithPassword` + `verifyOtp({type:'signup'|'email'})` + fallback `POST /api/auth/{signup,signin,request-otp,verify-otp}` + `POST /api/auth/supabase-sync` to get Python JWT for DB.
- **No hardcoded URLs/secrets:** `Website/js/config.js` dynamically resolves `API_BASE` (same-origin in prod, `http://127.0.0.1:8000` for Live Server `5500`). Backend loads `.env` via `python-dotenv`; `backend/.env.example` provided, `backend/.env` ignored.
- **Python-only backend:** all DB/logic via FastAPI (`backend/main.py:1`), Supabase Postgres via `psycopg2`, Gemini for generation/evaluation/summary. No Node backend.
- **Pricing:** modern dark 3-tier (`Free $0` / `Pro $9` popular / `Team $29`) with `linear-gradient` and `✓` features.

---

## 🏗 Architecture

```
Website/ (static)
  js/config.js      → dynamic API_BASE, fetchApi()
  js/supabase.js    → init from /api/config, getSupabase(), requireAuth()
  dashboard.html    → role grid, skills grid, test (12+3), result (human), aiStateCard, History/Pricing/Account views
  get-started.html  → Supabase signUp + Python OTP (dual verify)
  signin.html       → Supabase signInWithPassword + OTP + passwordless fallback
Dataset/data.json   → 160 roles × weighted skills (1-5), 216 skills with aliases
backend/
  main.py           → FastAPI 2.0, CORS, startup init_db, mounts /app static, sys.path fix for `backend.main:app` vs `main:app`
  app/config.py     → loads Dataset, env via dotenv, no hardcodes
  app/db.py         → get_conn(), init_db() creates profiles, analyses, otp_codes, test_history
  app/routes/auth.py → /api/auth/{signup,signin,request-otp,verify-otp,supabase-sync,me} (Supabase sync → Python JWT)
  app/routes/skill_test.py → /api/skill-test/{generate,evaluate,ai-summary} (12 MCQ + 3 text, Gemini with fallback mock)
  app/routes/history.py → /api/history POST/GET (proper DB)
  app/routes/roles.py, analyze.py, etc.
```

**Scoring:** `12 MCQ ×1 + 3 written ×2 = 18`. `Beginner 0-40% | Intermediate 41-70% | Advanced 71-85% | Expert 86-100%`.

---

## 🚀 Quick start

### 1. Env

```bash
cp backend/.env.example backend/.env
# fill:
# DATABASE_URL=postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres
# SECRET_KEY=random-string
# SUPABASE_URL=https://xxx.supabase.co
# SUPABASE_ANON_KEY=eyJ...
# GEMINI_API_KEY=...
# GEMINI_MODEL=gemini-1.5-flash
```

### 2. Backend (Python only)

```bash
pip install -r backend/requirements.txt  # fastapi, uvicorn[standard], psycopg2-binary, python-jose, passlib, python-dotenv, httpx, PyPDF2

# from project root (recommended, now fixed for ModuleNotFoundError)
uvicorn backend.main:app --reload --port 8001 --host 127.0.0.1 --reload-dir backend
# OR from backend/
# uvicorn main:app --reload --port 8001

# health
curl http://127.0.0.1:8001/api/health
curl http://127.0.0.1:8001/api/config  # returns supabase_url/anon safely
```

> `WinError 10013` on `8000` → Windows reserves it. Use `8001`/`5000` or `netstat -ano | findstr :8000` → `taskkill /PID <PID> /F` or run PowerShell as Admin. `Website/js/config.js:11` auto-falls back to `8000` for `5500`, so if you run backend on `8001` set `window.API_BASE="http://127.0.0.1:8001"` before load or edit config.

### 3. Frontend

- **Single-origin (prod):** FastAPI mounts `Website` at `http://127.0.0.1:8001/app/dashboard.html`
- **Dev (Live Server):** `http://127.0.0.1:5500/Website/dashboard.html` → `js/config.js` proxies to `http://127.0.0.1:8001`

Flow: `Get Started` → pick role (search) → pick skills (search 216 + custom) → `Take skill test` → answer 12 MCQ (click) + 3 written (2-3 sentences) → `Submit` → `Test complete` (human) → `See my AI current state` → Dashboard AI card + History saved to Postgres.

---

## 🔐 Auth

- **Supabase Auth** (`supabase-js@2` from CDN, init via `/api/config`): `signUp({email, password, data:{full_name}})`, `signInWithPassword`, `signInWithOtp`, `verifyOtp({type:'signup'|'email'})`.
- **Python OTP** (`public.otp_codes`): `POST /api/auth/request-otp` (6-digit, 10min, dev returns `debug_otp`), `POST /api/auth/verify-otp`. Verified on both paths → `POST /api/auth/supabase-sync` → Python JWT (`skilly_token`) for DB.
- **Demo:** `Continue as demo` → `demo-token` + local fallback (no DB history).

---

## 📊 API

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | no | DB connectivity |
| GET | `/api/config` | no | `supabase_url`/`anon` + features (no secrets) |
| POST | `/api/auth/signup` | no | email/pass → OTP (Python) |
| POST | `/api/auth/signin` | no | email/pass → OTP |
| POST | `/api/auth/request-otp` | no | send OTP |
| POST | `/api/auth/verify-otp` | no | verify → `access_token` (Python JWT) |
| POST | `/api/auth/supabase-sync` | no | `email,supabase_user_id` → Python JWT |
| GET | `/api/auth/me` | Bearer | current user |
| POST | `/api/skill-test/generate` | no | 12 MCQ + 3 text |
| POST | `/api/skill-test/evaluate` | no | MCQ 1pt + text 0-2 |
| POST | `/api/skill-test/ai-summary` | no | role skills + claimed + test → AI JSON |
| POST | `/api/history` | Bearer | save test |
| GET | `/api/history` | Bearer | list 20 |
| GET | `/api/roles` | no | 160 roles |
| GET | `/api/skills` | no | 216 skills |

---

## 🗃 DB (Supabase Postgres)

`init_db()` creates if not exists:

- `profiles(id UUID PK, email UNIQUE, full_name, password_hash, is_verified BOOL, created_at)`
- `analyses(...)` (gap analysis)
- `otp_codes(id, email, code, expires_at, verified, attempts)`
- `test_history(id, user_id FK, target_role, claimed_skills JSONB, score/total/percentage/level, mcq_score/text_points, per_skill JSONB, strengths/weaknesses JSONB, ai_summary JSONB, created_at)` + indexes

All via `psycopg2` (Python only). History is **not** `localStorage` (kept only as demo fallback).

---

## 🎨 Frontend notes

- Premium dark SaaS (`#0A0A0A`, `#C7D6CF`, `#242629`, `Syne`/`Helvetica`), `bg-glow`, `choice-card selected`, `q-opt selected`, `q-text-input filled`.
- Search icon preserved as your fixed SVG (22px circle, `rgba(199,214,207,0.06)`).
- `js/config.js` handles `API_BASE` dynamically; `fetchApi()` falls back to `8000` if `5500` fails.

---

## 🙈 .gitignore

`.agents/`, `.opencode/`, `.claude/`, `skills-lock.json` (MCP), `temp/`, `fix_*.py`, `test_*.py`, `__pycache__/`, `.env`, `venv/` etc. are now properly ignored and untracked (`git rm --cached`). See `.gitignore:1`.

---

## 📦 Deploy

- **Backend:** any Python host (`uvicorn backend.main:app --port $PORT --host 0.0.0.0`). Set env vars.
- **Frontend:** static `Website/` can be GitHub Pages, but needs backend URL → set `window.API_BASE="https://api.yourdomain"` before `config.js` or edit `js/config.js`.
- Repo: `https://github.com/aryaniiil/hackathon` (single repo, `main` branch, 1 commit → now 2nd commit with major update).

---

## 📝 License

Hackathon demo — MIT.

