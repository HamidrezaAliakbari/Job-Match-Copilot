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

app = FastAPI(title="Job-Match Copilot API", version="beta-02")

# --------- Models ----------
class ResumeObj(BaseModel):
    summary: Optional[str] = ""
    skills: Optional[List[str]] = []
    experience_bullets: Optional[List[str]] = []
    projects: Optional[List[str]] = []
    education: Optional[List[str]] = []
    courses: Optional[List[str]] = []

class JobObj(BaseModel):
    title: Optional[str] = "Job"
    requirements: Optional[List[str]] = []
    preferred: Optional[List[str]] = []

class ScoreRequest(BaseModel):
    resume: Optional[ResumeObj] = None
    job: Optional[JobObj] = None
    resume_path: Optional[str] = None
    job_path: Optional[str] = None
    # legacy convenience fields (UI often posts plain text)
    resume_text: Optional[str] = None
    job_text: Optional[str] = None
    # optional explicit lists (overrides extracted ones)
    requirements: Optional[List[str]] = None
    preferred: Optional[List[str]] = None

    @validator("*", pre=True)
    def _strip_none(cls, v):
        return v

def _resolve_resume(req: ScoreRequest) -> Dict:
    if req.resume:
        return req.resume.model_dump()
    # allow text > parse
    if req.resume_text or req.resume_path:
        return parse_resume(req.resume_path, text=req.resume_text)
    raise HTTPException(status_code=422, detail="Provide resume or resume_path or resume_text")

def _resolve_job(req: ScoreRequest) -> Dict:
    if req.job and (req.job.requirements or req.job.preferred):
        # explicit object wins, but ensure headers are stripped by parser
        return parse_job(text="\n".join((req.job.requirements or []) + (req.job.preferred or [])),
                         requirements=req.job.requirements,
                         preferred=req.job.preferred)
    if req.job_text or req.job_path:
        return parse_job(req.job_path, text=req.job_text,
                         requirements=req.requirements, preferred=req.preferred)
    # final fallback: if caller only provided explicit arrays
    if req.requirements or req.preferred:
        return parse_job(text="\n".join((req.requirements or []) + (req.preferred or [])),
                         requirements=req.requirements, preferred=req.preferred)
    raise HTTPException(status_code=422, detail="Provide job or job_path or job_text or explicit requirements")

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
