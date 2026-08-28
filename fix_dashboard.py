import pathlib
path = pathlib.Path(r"D:\Hackathon\Website\dashboard.html")
content = path.read_text(encoding="utf-8")

# Fix generateAiSummary to properly push to DB and avoid historyEntry
# Replace the old inside that still references historyEntry

# First ensure function signature is with 2 args
if "async function generateAiSummary(testResult, answersDetail, historyEntry)" in content:
    content = content.replace("async function generateAiSummary(testResult, answersDetail, historyEntry)", "async function generateAiSummary(testResult, answersDetail)")
    print("fixed signature")

# Now replace the try block content that still uses historyEntry
old_try = """      try {
        const res = await window.fetchApi("/api/skill-test/ai-summary", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({
            target_role: onboardingRole,
            claimed_skills: Array.from(onboardingSkills),
            test_result: testResult,
            answers_detail: answersDetail
          })
        });
        const ai = await res.json();
        if (!res.ok) throw new Error(ai.detail || "AI summary failed");
        localStorage.setItem("skilly_ai_state", JSON.stringify(ai));
        // also store ai in history entry
        const hist = getHistory();
        const idx = hist.findIndex(h=> h.id===historyEntry.id);
        if (idx>=0) { hist[idx].ai = ai; localStorage.setItem("skilly_history", JSON.stringify(hist)); }
        renderAiState(ai);
      } catch (e) {
        console.log("AI summary failed", e);
        const gapFallback = { readiness: testResult.percentage || 60, strong:[], missing:[], total_skills:12 };
        const fallbackAi = {
          role: onboardingRole,
          readiness: testResult.percentage || 60,
          level: testResult.level || "Intermediate",
          level_description: testResult.level_description || "",
          summary: `Based on your test (${testResult.score}/${testResult.total} • ${testResult.level}), you have solid grounding in ${Array.from(onboardingSkills).slice(0,3).join(", ")}. Your written answers show ${testResult.text_points}/${testResult.text_max} reasoning points. Focus on missing role skills next.`,
          what_you_have: Array.from(onboardingSkills).slice(0,3),
          what_you_lack: (testResult.weaknesses||[]).slice(0,3),
          strengths: testResult.strengths||[],
          gaps: testResult.weaknesses||[],
          recommendation: testResult.recommendation || "Prioritize your weakest skills with projects.",
          next_steps: (testResult.weaknesses||["practice"]).slice(0,3).map(s=> `Practice ${s} with a hands-on project (1-2 weeks)`),
          validation_note: `Claimed ${onboardingSkills.size} skills; test validates ${testResult.strengths?.length||0} as strong.`,
          gap: gapFallback
        };
        localStorage.setItem("skilly_ai_state", JSON.stringify(fallbackAi));
        const hist = getHistory();
        const idx = hist.findIndex(h=> h.id===historyEntry.id);
        if (idx>=0) { hist[idx].ai = fallbackAi; localStorage.setItem("skilly_history", JSON.stringify(hist)); }
        renderAiState(fallbackAi);
      } finally {
        proc.style.display = "none";
      }"""

new_try = """      let ai = null;
      try {
        const res = await window.fetchApi("/api/skill-test/ai-summary", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({
            target_role: onboardingRole,
            claimed_skills: Array.from(onboardingSkills),
            test_result: testResult,
            answers_detail: answersDetail
          })
        });
        ai = await res.json();
        if (!res.ok) throw new Error(ai.detail || "AI summary failed");
        localStorage.setItem("skilly_ai_state", JSON.stringify(ai));
      } catch (e) {
        console.log("AI summary failed, using fallback", e);
        const gapFallback = { readiness: testResult.percentage || 60, strong:[], missing:[], total_skills:12 };
        ai = {
          role: onboardingRole,
          readiness: testResult.percentage || 60,
          level: testResult.level || "Intermediate",
          level_description: testResult.level_description || "",
          summary: `Based on your test (${testResult.score}/${testResult.total} • ${testResult.level}), you have solid grounding in ${Array.from(onboardingSkills).slice(0,3).join(", ")}. Your written answers show ${testResult.text_points}/${testResult.text_max} reasoning points. Focus on missing role skills next.`,
          what_you_have: Array.from(onboardingSkills).slice(0,3),
          what_you_lack: (testResult.weaknesses||[]).slice(0,3),
          strengths: testResult.strengths||[],
          gaps: testResult.weaknesses||[],
          recommendation: testResult.recommendation || "Prioritize your weakest skills with projects.",
          next_steps: (testResult.weaknesses||["practice"]).slice(0,3).map(s=> `Practice ${s} with a hands-on project (1-2 weeks)`),
          validation_note: `Claimed ${onboardingSkills.size} skills; test validates ${testResult.strengths?.length||0} as strong.`,
          gap: gapFallback
        };
        localStorage.setItem("skilly_ai_state", JSON.stringify(ai));
      }
      // Save to proper DB (Postgres via Python) - not just localStorage
      const entry = {
        id: Date.now().toString(),
        date: new Date().toISOString(),
        role: onboardingRole,
        skills: Array.from(onboardingSkills),
        score: testResult.score,
        total: testResult.total,
        percentage: testResult.percentage,
        level: testResult.level,
        mcq_score: testResult.mcq_score,
        mcq_total: testResult.mcq_total,
        text_points: testResult.text_points,
        text_max: testResult.text_max,
        strengths: testResult.strengths,
        weaknesses: testResult.weaknesses,
        recommendation: testResult.recommendation,
        level_description: testResult.level_description,
        text_feedback: testResult.text_feedback,
        per_skill: testResult.per_skill,
        ai: ai
      };
      try { await pushHistory(entry); } catch (err) { console.warn("pushHistory failed", err); }
      renderAiState(ai);
      proc.style.display = "none";"""

if old_try in content:
    content = content.replace(old_try, new_try)
    print("replaced try block")
else:
    print("old_try not found")
    # debug
    print(repr(content[content.find("async function generateAiSummary"):content.find("async function generateAiSummary")+500]))

# Also fix showResult push
old_show = """      document.getElementById("resultReco").textContent = result.recommendation || "Keep practicing your weakest skills with small projects.";
      dialog.dataset.answersDetail = JSON.stringify(answersDetail||[]);
      document.getElementById("resultContinueBtn").onclick = async () => {
        dialog.classList.remove("active");
        localStorage.setItem("skilly_onboarding_done", "true");
        // Push to history now
        const entry = {
          id: Date.now().toString(),
          date: new Date().toISOString(),
          role: onboardingRole,
          skills: Array.from(onboardingSkills),
          score: result.score,
          total: result.total,
          percentage: result.percentage,
          level: result.level,
          mcq_score: result.mcq_score,
          mcq_total: result.mcq_total,
          text_points: result.text_points,
          text_max: result.text_max,
          strengths: result.strengths,
          weaknesses: result.weaknesses,
          recommendation: result.recommendation,
          level_description: result.level_description,
          text_feedback: result.text_feedback,
          per_skill: result.per_skill
        };
        pushHistory(entry);
        // Now call AI summary with this entry
        await generateAiSummary(result, answersDetail, entry);
      };"""

new_show = """      document.getElementById("resultReco").textContent = result.recommendation || "Keep practicing your weakest skills with small projects.";
      dialog.dataset.answersDetail = JSON.stringify(answersDetail||[]);
      document.getElementById("resultContinueBtn").onclick = async () => {
        dialog.classList.remove("active");
        localStorage.setItem("skilly_onboarding_done", "true");
        // Defer history save until AI summary is ready (so DB entry includes AI)
        await generateAiSummary(result, answersDetail);
      };"""

if old_show in content:
    content = content.replace(old_show, new_show)
    print("replaced showResult")
else:
    print("old_show not found")

path.write_text(content, encoding="utf-8")
print("done")
