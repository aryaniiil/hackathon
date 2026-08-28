import os
import json
import re
import httpx
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any, Dict, Union

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)

router = APIRouter(prefix="/api/skill-test", tags=["skill-test"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
FALLBACK_MODELS = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro", "gemini-pro"]

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompt.md"
PROMPT_TMPL = ""
try:
    with open(PROMPT_PATH, encoding="utf-8") as f:
        PROMPT_TMPL = f.read()
except:
    try:
        with open(Path(__file__).parent / ".." / ".." / "prompt.md", encoding="utf-8") as f:
            PROMPT_TMPL = f.read()
    except:
        PROMPT_TMPL = ""

class GenerateIn(BaseModel):
    skills: List[str]
    target_role: Optional[str] = None

class EvaluateIn(BaseModel):
    questions: List[dict]
    answers: List[Any]  # int for mcq, str for text
    skills: Optional[List[str]] = None
    target_role: Optional[str] = None

class AiSummaryIn(BaseModel):
    target_role: str
    claimed_skills: List[str]
    test_result: Optional[Dict[str, Any]] = None
    answers_detail: Optional[List[Dict[str, Any]]] = None  # detailed Q+A with text
    gap: Optional[Dict[str, Any]] = None

def build_prompt(skills, target_role=None):
    skills_str = ", ".join(skills)
    role_str = f" for target role '{target_role}'" if target_role else ""
    # New prompt: 12 MCQ + 3 TEXT = 15 total
    return f"""You are an expert technical interviewer for skilly - are you industry ready.

Generate EXACTLY 15 questions to assess the user's skill level{role_str} in these skills: {skills_str}.

STRICT COMPOSITION:
- 12 Multiple Choice (type="mcq"): 4 easy, 4 medium, 4 hard. Each with 4 options, exactly one correct.
- 3 Text Input (type="text"): open-ended reasoning, 2-3 sentence answer expected. Difficulty: 2 medium, 1 hard. These test deeper reasoning, scenario handling, trade-offs, debugging explanation.

Requirements:
- Distribute evenly across all listed skills.
- For each skill, include at least one MCQ and consider one text if relevant.
- MCQ must test practical understanding, not trivial definitions. Options plausible.
- TEXT must ask to explain reasoning, compare options, debug, or describe approach (e.g., "In 2-3 sentences, explain how you would...") Provide a short guidance and placeholder.
- Return ONLY valid JSON array, no markdown.

Format for MCQ:
{{
  "id": 1,
  "skill": "python",
  "difficulty": "easy",
  "type": "mcq",
  "question": "...",
  "options": ["A", "B", "C", "D"],
  "correct_index": 0,
  "explanation": "brief why"
}}
Format for TEXT:
{{
  "id": 13,
  "skill": "python",
  "difficulty": "medium",
  "type": "text",
  "question": "In 2-3 sentences, explain how you would handle ... in Python?",
  "placeholder": "Explain your approach...",
  "guidance": "Expect mention of try/except, context managers...",
  "max_words": 80
}}

Ensure exactly 15 items, 12 with type mcq and 3 with type text. Use skill names exactly as provided: {skills_str}.
"""

def build_evaluate_prompt(questions, answers, skills, target_role):
    qna = []
    mcq_correct = 0
    mcq_total = 0
    text_entries = []
    for i, q in enumerate(questions):
        ans = answers[i] if i < len(answers) else None
        qtype = q.get("type", "mcq")
        if qtype == "text":
            user_text = ans if isinstance(ans, str) else str(ans) if ans is not None else ""
            text_entries.append(f"Q{i+1} [TEXT {q['skill']} - {q['difficulty']}] : {q['question']} | User answer: \"{user_text[:400]}\"")
        else:
            mcq_total += 1
            ans_idx = ans if isinstance(ans, int) else -1
            try:
                user_ans = q["options"][ans_idx] if 0 <= ans_idx < len(q["options"]) else "No answer"
                correct = q["options"][q["correct_index"]]
                result = "CORRECT" if ans_idx==q["correct_index"] else "WRONG"
                if result=="CORRECT":
                    mcq_correct += 1
            except:
                user_ans = "No answer"
                correct = q.get("options", ["",""])[0]
                result = "WRONG"
            qna.append(f"Q{i+1} [{q['skill']} - {q['difficulty']}] : {q['question']} | User: {user_ans} | Correct: {correct} | Result: {result}")
    qna_str = "\n".join(qna) if qna else "No MCQ"
    text_str = "\n".join(text_entries) if text_entries else "No text questions"
    skills_str = ", ".join(skills) if skills else "general"
    role_part = f" for role {target_role}" if target_role else ""
    prompt = f"You are an expert evaluator for skilly.\n\n"
    prompt += f"User was tested on skills: {skills_str}{role_part} with 12 MCQ + 3 TEXT (total 15, max points 18: MCQ 1pt each, TEXT 0-2pts each).\n\n"
    prompt += f"MCQ Results:\n{qna_str}\n\n"
    prompt += f"TEXT Answers to evaluate (score each 0=poor/blank, 1=partial, 2=good with reasoning):\n{text_str}\n\n"
    prompt += f"MCQ Score: {mcq_correct}/{mcq_total}\n\n"
    prompt += "Task: Evaluate overall level. Score TEXT answers based on reasoning quality, correctness, depth.\n"
    prompt += "Return ONLY JSON:\n"
    prompt += '{\n  "mcq_score": 8,\n  "mcq_total": 12,\n  "text_scores": [2,1,0],\n  "text_total": 3,\n  "text_points": 3,\n  "text_max": 6,\n  "score": 11,\n  "total": 18,\n  "percentage": 61,\n  "level": "Intermediate",\n  "level_description": "one sentence",\n  "strengths": ["skill1"],\n  "weaknesses": ["skill1"],\n  "per_skill": {"python": {"correct": 3, "total": 4, "text_avg": 1.5, "level": "Intermediate"}},\n  "text_feedback": [{"id":13, "score":1, "feedback":"Good but missing X"} ],\n  "recommendation": "2-3 sentences"\n}\n\n'
    prompt += "Levels: Beginner 0-40%, Intermediate 41-70%, Advanced 71-85%, Expert 86-100%. Be strict but fair.\n"
    prompt += "Include per_skill level based on combined MCQ + TEXT for that skill.\n"
    return prompt

def build_ai_summary_prompt(target_role: str, claimed_skills: List[str], role_skills: dict, test_result: dict, gap: dict, answers_detail: list):
    role_skills_str = ", ".join([f"{k}:{v}" for k,v in role_skills.items()]) if role_skills else "unknown"
    claimed_str = ", ".join(claimed_skills) if claimed_skills else "none"
    # gap
    strong = ", ".join([s.get("skill", s.get("label","")) for s in gap.get("strong", [])]) if gap else "none"
    partial = ", ".join([s.get("skill","") for s in gap.get("partial", [])]) if gap else "none"
    missing = ", ".join([s.get("skill","") for s in gap.get("missing", [])]) if gap else "none"
    readiness = gap.get("readiness", "?") if gap else "?"
    # test
    test_summary = "No test taken"
    per_skill_str = ""
    strengths = ""
    weaknesses = ""
    level = "Unknown"
    pct = "?"
    text_fb = ""
    if test_result:
        level = test_result.get("level", "Unknown")
        pct = test_result.get("percentage", "?")
        score = test_result.get("score", "?")
        total = test_result.get("total", "?")
        test_summary = f"Score {score}/{total} ({pct}%) Level {level}"
        per = test_result.get("per_skill", {})
        per_skill_str = json.dumps(per, indent=2)[:1800]
        strengths = ", ".join(test_result.get("strengths", []))
        weaknesses = ", ".join(test_result.get("weaknesses", []))
        text_fb = json.dumps(test_result.get("text_feedback", [])[:3])[:1000]
    # answers detail for text
    text_answers = ""
    if answers_detail:
        for item in answers_detail[:4]:
            q = item.get("question","")[:120]
            ans = str(item.get("answer",""))[:300]
            typ = item.get("type","mcq")
            text_answers += f"- [{typ}] {q} -> {ans}\n"
    prompt = f"""You are skilly AI career analyst. Assess user's CURRENT STATE honestly and constructively.

Context:
- Target Role: {target_role}
- Role requires (skill:weight): {role_skills_str}
- User claimed skills: {claimed_str}
- Gap analysis: readiness {readiness}% | Strong: {strong} | Partial: {partial} | Missing (gaps): {missing}
- Test result: {test_summary}
- Strengths per test: {strengths or 'none'}
- Weaknesses per test: {weaknesses or 'none'}
- Per-skill breakdown: {per_skill_str}
- Text feedback: {text_fb}
- Sample answers (reasoning): 
{text_answers}

Task: Synthesize into current state report. Be specific to role requirements. Acknowledge claimed vs demonstrated (test) gap. Don't hallucinate.

Return ONLY JSON:
{{
  "summary": "3-4 sentence holistic current state, mention role fit and test validation",
  "readiness": 68,
  "level": "Intermediate",
  "level_description": "one sentence calibrated",
  "what_you_have": ["skill1", "skill2"],
  "what_you_lack": ["skill1", "skill2"],
  "strengths": ["skill1 with why"],
  "gaps": ["skill1 with why it matters for role"],
  "recommendation": "3-4 sentence personalized next steps focusing on highest-weight missing + weakest test areas",
  "next_steps": ["Step 1: Learn X via project Y (1-2 weeks)", "Step 2: Practice Z", "Step 3: ..."],
  "confidence": "high or medium",
  "validation_note": "1 sentence comparing claimed vs test-demonstrated skill"
}}

Rules:
- readiness 0-100 based on role weight coverage + test performance (weighted).
- what_you_have = claimed + demonstrated strong (intersection).
- what_you_lack = missing sorted by weight + test weaknesses.
- next_steps 3 items, ordered by priority weight.
- Keep concise, actionable.
"""
    return prompt

async def call_gemini(prompt: str, model: str = None):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=502, detail="Gemini API key not configured")
    target_model = model or GEMINI_MODEL
    models_to_try = [target_model] + [m for m in FALLBACK_MODELS if m != target_model]
    last_err = None
    for m in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}

]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}
            }
            async with httpx.AsyncClient(timeout=40) as client:
                r = await client.post(url, json=payload)
                if r.status_code != 200:
                    last_err = f"{m} failed {r.status_code}: {r.text[:400]}"
                    continue
                data = r.json()
                # handle blocked or no candidates
                cands = data.get("candidates", [])
                if not cands:
                    last_err = f"{m} no candidates: {json.dumps(data)[:400]}"
                    continue
                text = cands[0]["content"]["parts"][0]["text"]
                return text, m
        except HTTPException:
            raise
        except Exception as e:
            last_err = str(e)
            continue
    raise HTTPException(status_code=502, detail=f"Gemini failed: {last_err}")

def extract_json_array(text: str):
    text = text.strip()
    text = re.sub(r"```(?:json)?", "", text)
    text = re.sub(r"```", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except:
            pass
    try:
        return json.loads(text)
    except:
        raise

def extract_json_obj(text: str):
    text = text.strip()
    text = re.sub(r"```(?:json)?", "", text)
    text = re.sub(r"```", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        candidate = text[start:end+1]
        try:
            return json.loads(candidate)
        except:
            pass
    return json.loads(text)

def mock_questions(skills):
    """Fallback: 12 MCQ + 3 TEXT"""
    mcq_pool = {
        "python": [
            ("Which keyword defines a function in Python?", ["function myFunc():", "def myFunc():", "create myFunc():", "func myFunc():"], 1),
            ("What does 3 * 'a' produce?", ["'aaa'", "9", "TypeError", "'a3'"], 0),
            ("Lists vs tuples?", ["Tuples mutable, lists immutable", "Lists mutable, tuples immutable", "No difference", "Tuples only ints"], 1),
            ("Output of [x for x in range(5) if x%2==0]?", ["[0, 2, 4]", "[1, 3]", "[0,1,2,3,4]", "[2,4]"], 0),
            ("Which handles errors?", ["try/except", "catch/throw", "if/else", "for/while"], 0),
            ("What is a decorator?", ["Function wrapping another", "Variable", "Loop", "Class"], 0),
        ],
        "javascript": [
            ("Purpose of useState?", ["Side effects", "Fetch data", "Add state to functional components", "Pass down data"], 2),
            ("What does 'let' do?", ["Block-scoped variable", "Constant", "No such keyword", "Global variable"], 0),
            ("How to pass data parent->child?", ["State", "Props", "Context", "Redux"], 1),
            ("What is closure?", ["Function with access to outer scope", "Loop", "Variable", "Class"], 0),
            ("push() does what?", ["Adds to end", "Removes last", "Adds to start", "Removes first"], 0),
            ("What is event loop?", ["Handles async callbacks", "Loop syntax", "Variable", "CSS"], 0),
        ],
        "sql": [
            ("Which extracts data?", ["GET", "OPEN", "EXTRACT", "SELECT"], 3),
            ("Which JOIN returns all when match in either?", ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN"], 3),
            ("Purpose of GROUP BY?", ["Filter rows", "Sort results", "Group rows with same values", "Join tables"], 2),
            ("Which filters groups?", ["WHERE", "HAVING", "FILTER", "GROUP"], 1),
            ("PRIMARY KEY ensures?", ["Duplicate allowed", "Unique and not null", "Only numbers", "No index"], 1),
            ("What is window function?", ["Operates over set of rows", "Only SELECT", "No such", "Loop"], 0),
        ],
        "react": [
            ("Purpose of useState?", ["Side effects", "Fetch data", "Add state to functional components", "Pass data"], 2),
            ("When cleanup runs?", ["Only mount", "Only error", "Before unmount and before re-running", "Only after"], 2),
            ("What is JSX?", ["JavaScript XML syntax for React", "CSS framework", "Database", "Testing tool"], 0),
            ("Handle list keys?", ["Use index always", "Use stable unique key", "No key needed", "Use random"], 1),
            ("Virtual DOM?", ["Lightweight copy of real DOM", "Database", "Server", "Style sheet"], 0),
            ("What is prop drilling?", ["Passing props deep manually", "Database", "CSS", "Router"], 0),
        ],
    }
    generic_mcq = [
        ("What is a key best practice for {skill}?", ["Follow documentation", "Ignore standards", "Hardcode everything", "Skip testing"], 0),
        ("Which tool commonly used with {skill}?", ["Popular tool A", "Unrelated tool", "Deprecated tool", "No tool"], 0),
        ("Common pitfall in {skill}?", ["Poor error handling", "Perfect code", "No pitfalls", "Only syntax"], 0),
        ("How to improve {skill} performance?", ["Optimize and profile", "Add loops", "Ignore metrics", "Single thread only"], 0),
    ]
    text_templates = [
        ("In 2-3 sentences, explain how you would debug a {skill} issue where {scenario}?", "Explain debugging steps..."),
        ("Describe the trade-offs when choosing {skill} for {scenario} in 2-3 sentences.", "Discuss trade-offs..."),
        ("In 2-3 sentences, explain how you would implement {scenario} using {skill} and why?", "Describe approach..."),
    ]
    scenarios = {
        "python": "a function returns unexpected None",
        "javascript": "state updates don't re-render",
        "sql": "a query is slow on large tables",
        "react": "a component re-renders too often",
        "default": "performance degrades under load"
    }
    questions = []
    # 12 MCQ
    for i in range(12):
        skill = skills[i % len(skills)] if skills else "python"
        diff = "easy" if i < 4 else "medium" if i < 8 else "hard"
        if skill in mcq_pool:
            q, opts, corr = mcq_pool[skill][i % len(mcq_pool[skill])]
        elif skill.lower() in mcq_pool:
            q, opts, corr = mcq_pool[skill.lower()][i % len(mcq_pool[skill.lower()])]
        else:
            g = generic_mcq[i % len(generic_mcq)]
            q = g[0].format(skill=skill.replace("_"," "))
            opts = g[1]
            corr = g[2]
        questions.append({
            "id": i+1,
            "skill": skill,
            "difficulty": diff,
            "type": "mcq",
            "question": q,
            "options": opts,
            "correct_index": corr,
            "explanation": f"Tests {skill} {diff}."
        })
    # 3 TEXT
    for j in range(3):
        idx = 13 + j
        skill = skills[j % len(skills)] if skills else "python"
        diff = "medium" if j < 2 else "hard"
        scenario = scenarios.get(skill, scenarios.get(skill.lower(), scenarios["default"]))
        tmpl, placeholder = text_templates[j % len(text_templates)]
        q_text = tmpl.format(skill=skill.replace("_"," "), scenario=scenario)
        questions.append({
            "id": idx,
            "skill": skill,
            "difficulty": diff,
            "type": "text",
            "question": q_text,
            "placeholder": placeholder,
            "guidance": f"Expect reasoning about {skill}, mention trade-offs, steps.",
            "max_words": 80
        })
    return questions

def score_text_fallback(text: str) -> int:
    if not text or not text.strip():
        return 0
    t = text.strip()
    w = len(t.split())
    if w < 5:
        return 0
    if w < 12:
        return 1
    # check reasoning keywords
    keywords = ["because", "since", "therefore", "however", "trade", "approach", "would", "should", "using", "handle"]
    low = t.lower()
    hits = sum(1 for k in keywords if k in low)
    if w >= 20 and hits >= 2:
        return 2
    if w >= 12:
        return 1
    return 0

@router.post("/generate")
async def generate(data: GenerateIn):
    if not data.skills or len(data.skills) == 0:
        raise HTTPException(status_code=400, detail="Select at least one skill")
    skills = [s.strip() for s in data.skills if s.strip()][:8]
    prompt = build_prompt(skills, data.target_role)
    try:
        text, used_model = await call_gemini(prompt)
        questions = extract_json_array(text)
        if not isinstance(questions, list) or len(questions) < 10:
            raise ValueError("Invalid length")
        if len(questions) < 15:
            needed = 15 - len(questions)
            mock_pad = mock_questions(skills)
            for j in range(needed):
                mq = mock_pad[j % len(mock_pad)].copy()
                mq["id"] = len(questions) + 1
                mq["skill"] = skills[len(questions) % len(skills)]
                questions.append(mq)
        questions = questions[:15]
        # normalize and ensure 12 mcq + 3 text
        mcq_count = sum(1 for q in questions if q.get("type") == "mcq")
        text_count = sum(1 for q in questions if q.get("type") == "text")
        if mcq_count != 12 or text_count != 3:
            # force fallback to correct distribution if model didn't follow
            questions = mock_questions(skills)
        # final normalize
        for i, q in enumerate(questions):
            q["id"] = i+1
            if "skill" not in q:
                q["skill"] = skills[i % len(skills)]
            if "difficulty" not in q:
                q["difficulty"] = "easy" if i < 4 else "medium" if i < 11 else "hard"
            if q.get("type") not in ["mcq","text"]:
                q["type"] = "mcq" if i < 12 else "text"
            if q["type"] == "mcq":
                if "options" not in q or not isinstance(q["options"], list) or len(q["options"]) != 4:
                    q["options"] = ["Option A", "Option B", "Option C", "Option D"]
                if q.get("correct_index") not in [0,1,2,3]:
                    q["correct_index"] = 0
            else:
                if "placeholder" not in q:
                    q["placeholder"] = "Explain in 2-3 sentences..."
                if "guidance" not in q:
                    q["guidance"] = "Mention trade-offs and steps."
                if "max_words" not in q:
                    q["max_words"] = 80
        return {"questions": questions, "model": used_model, "skills": skills}
    except HTTPException as he:
        print(f"Gemini generate failed, mock: {he.detail}")
        return {"questions": mock_questions(skills), "model": "mock", "skills": skills, "fallback": True, "warning": str(he.detail)[:200]}
    except Exception as e:
        print(f"Generate error fallback: {e}")
        return {"questions": mock_questions(skills), "model": "mock", "skills": skills, "fallback": True}

@router.post("/evaluate")
async def evaluate(data: EvaluateIn):
    if not data.questions or len(data.questions) == 0:
        raise HTTPException(status_code=400, detail="No questions provided")
    if not data.answers or len(data.answers) != len(data.questions):
        raise HTTPException(status_code=400, detail="Answers length must match questions")
    # Separate counts
    mcq_total = sum(1 for q in data.questions if q.get("type","mcq") == "mcq")
    text_total = sum(1 for q in data.questions if q.get("type") == "text")
    prompt = build_evaluate_prompt(data.questions, data.answers, data.skills or [], data.target_role)
    try:
        text, used_model = await call_gemini(prompt)
        result = extract_json_obj(text)
        # --- Ensure all human-friendly fields exist even if Gemini omitted them ---
        # Compute local correct counts
        mcq_score_local = sum(1 for i,q in enumerate(data.questions) if q.get("type","mcq")=="mcq" and i < len(data.answers) and isinstance(data.answers[i], int) and data.answers[i]==q.get("correct_index"))
        # text scores local fallback
        text_scores_local = []
        for i,q in enumerate(data.questions):
            if q.get("type")=="text":
                ans = data.answers[i] if i < len(data.answers) else ""
                text_scores_local.append(score_text_fallback(str(ans) if ans is not None else ""))
        text_points_local = sum(text_scores_local)
        total_local = mcq_total + text_total*2 if (mcq_total+text_total)>0 else 15
        score_local = mcq_score_local + text_points_local
        pct_local = round(score_local/total_local*100) if total_local else 0

        # Fill missing top-level fields from local if Gemini omitted
        if "mcq_score" not in result or result.get("mcq_score") is None:
            result["mcq_score"] = result.get("mcq_score", mcq_score_local)
        if "mcq_total" not in result:
            result["mcq_total"] = mcq_total
        if "text_scores" not in result or not isinstance(result.get("text_scores"), list) or len(result.get("text_scores",[])) != text_total:
            # keep Gemini text_scores if valid else local
            if "text_scores" not in result or len(result.get("text_scores",[])) != text_total:
                result["text_scores"] = text_scores_local
        if "text_points" not in result:
            result["text_points"] = sum(result.get("text_scores", text_scores_local))
        if "text_total" not in result:
            result["text_total"] = text_total
        if "text_max" not in result:
            result["text_max"] = text_total*2
        if "score" not in result:
            result["score"] = result.get("score", score_local)
        if "total" not in result:
            result["total"] = result.get("total", total_local)
        if "percentage" not in result:
            result["percentage"] = round(result["score"]/result["total"]*100) if result["total"] else pct_local
        # If Gemini gave unrealistic score (e.g., handles 15 instead of 18), normalize
        if result.get("total") == 15 and total_local == 18:
            # Gemini used old 15 scale, convert: keep percentage but fix totals for display
            result["total"] = total_local
            # score remains as is but percentage already correct; ensure text fields consistent
            if result.get("text_points", 0) == 0 and text_points_local>0:
                result["text_points"] = text_points_local
                result["text_scores"] = text_scores_local
                result["score"] = result.get("mcq_score",0) + result["text_points"]
                result["percentage"] = round(result["score"]/result["total"]*100)

        if "level" not in result:
            pct = result.get("percentage", pct_local)
            if pct <= 40: result["level"] = "Beginner"
            elif pct <= 70: result["level"] = "Intermediate"
            elif pct <= 85: result["level"] = "Advanced"
            else: result["level"] = "Expert"
        if "level_description" not in result or not result.get("level_description"):
            pct = result.get("percentage", 0)
            lvl = result.get("level","Intermediate")
            result["level_description"] = f"You scored {result.get('score')}/{result.get('total')} ({pct}%). This is {lvl} level — {'keep building fundamentals' if lvl=='Beginner' else 'solid foundation, now refine strengths' if lvl=='Intermediate' else 'strong — polish advanced gaps' if lvl=='Advanced' else 'expert — ready for high-impact roles'}."
        # Ensure strengths/weaknesses exist
        if "strengths" not in result or "weaknesses" not in result:
            # will be filled via per_skill fallback below
            pass
        # Human-friendly recommendation fallback
        if "recommendation" not in result or not result.get("recommendation"):
            result["recommendation"] = "Focus on your weakest skills with hands-on projects and revisit reasoning questions with trade-offs."
        result["model"] = used_model
        # ensure per_skill exists and is human-friendly
        if "per_skill" not in result or not isinstance(result.get("per_skill"), dict):
            from collections import defaultdict
            per = defaultdict(lambda: {"correct":0, "total":0, "text_scores":[]})
            for i,q in enumerate(data.questions):
                s = q.get("skill","general")
                per[s]["total"] += 1
                if q.get("type")=="text":
                    text_idx = sum(1 for j in range(i) if data.questions[j].get("type")=="text")
                    sc = result.get("text_scores", text_scores_local)[text_idx] if text_idx < len(result.get("text_scores", text_scores_local)) else 0
                    per[s]["text_scores"].append(sc)
                else:
                    if i < len(data.answers) and isinstance(data.answers[i], int) and data.answers[i]==q.get("correct_index"):
                        per[s]["correct"] += 1
            per_skill = {}
            for k,v in per.items():
                p = round((v["correct"] + sum(v["text_scores"])/2)/v["total"]*100) if v["total"] else 0
                lvl = "Beginner" if p <=40 else "Intermediate" if p<=70 else "Advanced" if p<=85 else "Expert"
                per_skill[k] = {"correct": v["correct"], "total": v["total"], "text_avg": round(sum(v["text_scores"])/len(v["text_scores"]),1) if v["text_scores"] else 0, "level": lvl}
            result["per_skill"] = per_skill
        else:
            # Normalize per_skill to ensure each has correct/total/text_avg/level
            for k,v in list(result["per_skill"].items()):
                if "level" not in v:
                    p = round((v.get("correct",0) + v.get("text_avg",0)/2)/v.get("total",1)*100) if v.get("total") else 0
                    v["level"] = "Beginner" if p <=40 else "Intermediate" if p<=70 else "Advanced" if p<=85 else "Expert"
                if "text_avg" not in v:
                    v["text_avg"] = 0
        # Ensure text_feedback exists
        if "text_feedback" not in result or not isinstance(result["text_feedback"], list):
            result["text_feedback"] = []
            idx = 0
            for i,q in enumerate(data.questions):
                if q.get("type")=="text":
                    sc = result.get("text_scores", text_scores_local)[idx] if idx < len(result.get("text_scores", text_scores_local)) else 0
                    fb = "Great reasoning with trade-offs." if sc==2 else "Good start — add more specific steps and why." if sc==1 else "Try to explain in 2-3 sentences with steps and trade-offs."
                    result["text_feedback"].append({"id": q["id"], "skill": q["skill"], "score": sc, "feedback": fb})
                    idx+=1
        return result
    except Exception as e:
        print(f"Evaluate fallback due: {e}")
        # local fallback
        mcq_score = sum(1 for i,q in enumerate(data.questions) if q.get("type","mcq")=="mcq" and i < len(data.answers) and data.answers[i]==q.get("correct_index"))
        text_scores = []
        for i,q in enumerate(data.questions):
            if q.get("type")=="text":
                ans = data.answers[i] if i < len(data.answers) else ""
                text_scores.append(score_text_fallback(str(ans) if ans is not None else ""))
        text_points = sum(text_scores)
        total = mcq_total + text_total*2 if (mcq_total+text_total)>0 else 15
        score = mcq_score + text_points
        pct = round(score/total*100) if total else 0
        level = "Beginner" if pct <=40 else "Intermediate" if pct<=70 else "Advanced" if pct<=85 else "Expert"
        from collections import defaultdict
        per = defaultdict(lambda: {"correct":0, "total":0, "text_scores":[]})
        for i,q in enumerate(data.questions):
            s = q.get("skill","general")
            per[s]["total"] += 1
            if q.get("type")=="text":
                idx = sum(1 for j in range(i) if data.questions[j].get("type")=="text")
                sc = text_scores[idx] if idx < len(text_scores) else 0
                per[s]["text_scores"].append(sc)
            else:
                if i < len(data.answers) and data.answers[i]==q.get("correct_index"):
                    per[s]["correct"] += 1
        per_skill = {}
        for k,v in per.items():
            # estimate percentage
            text_avg = sum(v["text_scores"])/len(v["text_scores"]) if v["text_scores"] else 0
            # convert to points: correct + text_avg/2 approx?
            # total skills total includes both types, so max per skill total*? Simplify:
            p = round((v["correct"] + sum(v["text_scores"])/2)/v["total"]*100) if v["total"] else 0
            lvl = "Beginner" if p <=40 else "Intermediate" if p<=70 else "Advanced" if p<=85 else "Expert"
            per_skill[k] = {"correct": v["correct"], "total": v["total"], "text_avg": round(text_avg,1), "level": lvl}
        return {
            "mcq_score": mcq_score,
            "mcq_total": mcq_total,
            "text_scores": text_scores,
            "text_total": text_total,
            "text_points": text_points,
            "text_max": text_total*2,
            "score": score,
            "total": total,
            "percentage": pct,
            "level": level,
            "level_description": f"You scored {pct}% ({score}/{total}) - {level} level. MCQ {mcq_score}/{mcq_total}, Text {text_points}/{text_total*2}.",
            "strengths": [k for k,v in per_skill.items() if v["level"] in ["Advanced","Expert"]],
            "weaknesses": [k for k,v in per_skill.items() if v["level"] in ["Beginner"]],
            "per_skill": per_skill,
            "text_feedback": [{"id": q["id"], "score": text_scores[sum(1 for j in range(i) if data.questions[j].get("type")=="text")], "feedback": "Good reasoning" if text_scores[sum(1 for j in range(i) if data.questions[j].get("type")=="text")]>=1 else "Needs more depth and specifics."} for i,q in enumerate(data.questions) if q.get("type")=="text"],
            "recommendation": f"Focus on {', '.join([k for k,v in per_skill.items() if v['level']=='Beginner'][:2]) or 'your weakest skills'} next. Practice reasoning in text answers with trade-offs.",
            "model": "local-fallback",
            "fallback": True
        }

@router.post("/ai-summary")
async def ai_summary(data: AiSummaryIn):
    from app.utils import do_gap_analysis, find_role
    from app.config import ROLES, SKILLS_MAP
    # get role skills
    role_obj = find_role(data.target_role)
    if not role_obj:
        raise HTTPException(status_code=404, detail=f"Role '{data.target_role}' not found")
    role_skills = role_obj.get("skills", {})
    # compute gap if not provided
    gap = data.gap
    if not gap:
        try:
            gap = do_gap_analysis(data.target_role, data.claimed_skills or [])
        except Exception as e:
            gap = {"readiness": 0, "strong": [], "partial": [], "missing": [{"skill": k, "weight": v} for k,v in role_skills.items()]}
    # test result plus answers detail
    test_result = data.test_result or {}
    answers_detail = data.answers_detail or []
    prompt = build_ai_summary_prompt(data.target_role, data.claimed_skills, role_skills, test_result, gap, answers_detail)
    try:
        text, used_model = await call_gemini(prompt)
        result = extract_json_obj(text)
        # ensure fields
        if "readiness" not in result:
            result["readiness"] = gap.get("readiness", 0)
        if "level" not in result:
            result["level"] = test_result.get("level", "Intermediate")
        result["model"] = used_model
        result["role"] = data.target_role
        result["gap"] = gap
        return result
    except HTTPException as he:
        print(f"AI summary gemini failed: {he.detail}, using fallback")
        # fallback mock summary
        readiness = gap.get("readiness", 0)
        level = test_result.get("level", "Intermediate") if test_result else "Intermediate"
        pct = test_result.get("percentage", readiness) if test_result else readiness
        strengths = test_result.get("strengths", []) if test_result else [s["skill"] for s in gap.get("strong", [])[:2]]
        gaps_list = [s["skill"] for s in gap.get("missing", [])[:3]]
        # derive what_you_have / lack
        what_have = list(set(data.claimed_skills) & set([s["skill"] for s in gap.get("strong", [])]))[:4]
        if not what_have:
            what_have = [s["skill"] for s in gap.get("strong", [])[:3]]
        what_lack = gaps_list
        # fallback next steps from gaps
        next_steps = []
        for g in gaps_list[:3]:
            next_steps.append(f"Learn {g.replace('_',' ')} via hands-on project (1-2 weeks) - high weight for {data.target_role}")
        if not next_steps:
            next_steps = ["Practice weakest skill with project", "Review fundamentals", "Build portfolio piece"]
        return {
            "summary": f"You are preparing for {data.target_role} with {len(data.claimed_skills)} claimed skills. Your test shows {level} level ({pct}%). Readiness {readiness}% based on role coverage. Focus on top-weighted gaps to reach Advanced.",
            "readiness": readiness,
            "level": level,
            "level_description": test_result.get("level_description", f"{level} - {pct}% match") if test_result else f"{level} readiness",
            "what_you_have": what_have,
            "what_you_lack": what_lack,
            "strengths": strengths[:3] or what_have,
            "gaps": gaps_list,
            "recommendation": test_result.get("recommendation", f"Prioritize {', '.join(gaps_list[:2])} next. Build projects to demonstrate them and retake test to validate.") if test_result else f"Prioritize {', '.join(gaps_list[:2])}.",
            "next_steps": next_steps,
            "confidence": "medium",
            "validation_note": f"Claimed {len(data.claimed_skills)} skills; test validates {len(strengths)} as strong, {len(gaps_list)} gaps remain.",
            "model": "fallback",
            "fallback": True,
            "gap": gap,
            "role": data.target_role
        }
    except Exception as e:
        print(f"AI summary fallback due {e}")
        # same fallback as above
        readiness = gap.get("readiness", 0)
        level = test_result.get("level", "Intermediate") if test_result else "Intermediate"
        pct = test_result.get("percentage", readiness) if test_result else readiness
        gaps_list = [s["skill"] for s in gap.get("missing", [])[:3]]
        what_have = [s["skill"] for s in gap.get("strong", [])[:3]]
        return {
            "summary": f"Preparing for {data.target_role}. Readiness {readiness}%, test {level} ({pct}%).",
            "readiness": readiness,
            "level": level,
            "level_description": f"{level}",
            "what_you_have": what_have,
            "what_you_lack": gaps_list,
            "strengths": what_have,
            "gaps": gaps_list,
            "recommendation": f"Focus on {', '.join(gaps_list[:2])}.",
            "next_steps": [f"Learn {g}" for g in gaps_list[:3]],
            "confidence": "low",
            "validation_note": "Fallback summary.",
            "model": "fallback-error",
            "fallback": True,
            "gap": gap,
            "role": data.target_role
        }
