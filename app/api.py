from __future__ import annotations
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator

from core.parse_resume import parse_resume
from core.parse_job import parse_job
from core.reason_llm import evaluate_requirements
from core.score import compute_match_score
from core.counterfactual import generate_counterfactuals
from core.action import decide_action
import re
app = FastAPI(title="Job-Match Copilot API", version="beta-02")
# ---------- Light client-side sectionizers (UI only) ----------


# --------- Health ----------
@app.get("/healthz")
def healthz():
    return {"ok": True}

# --------- Score ----------
@app.post("/score")
def score_match(request: ScoreRequest):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        evals = evaluate_requirements(job.get("requirements") or [], resume,
                                      preferred=job.get("preferred") or [])
        agg = compute_match_score(evals)
        return {**agg, "evaluations": evals}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/score failed: {e}")

# --------- Counterfactual ----------
@app.post("/counterfactual")
def counterfactual(request: ScoreRequest):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        suggestions = generate_counterfactuals(resume, job)
        return {"suggestions": suggestions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/counterfactual failed: {e}")

# --------- Action ----------
@app.post("/action")
def action(request: ScoreRequest):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        evals = evaluate_requirements(job.get("requirements") or [], resume,
                                      preferred=job.get("preferred") or [])
        decision = decide_action(evals)
        return decision
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/action failed: {e}")
