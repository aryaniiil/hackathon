from fastapi import APIRouter, HTTPException
import httpx
from app.utils import canonical_skill

router = APIRouter(prefix="/api", tags=["github"])

@router.get("/github/{username}")
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
            skills = list(langs.keys())
            canonical_skills = [canonical_skill(s) or s for s in skills]
            return {"username": username, "repos_count": len(repos), "languages": langs, "skills": list(set(canonical_skills))}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
