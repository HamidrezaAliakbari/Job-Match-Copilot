# app/api.py
from __future__ import annotations
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from starlette.responses import PlainTextResponse, JSONResponse

from core.parse_resume import parse_resume
from core.parse_job import parse_job
from core.reason_llm import evaluate_requirements
from core.score import compute_match_score
from core.counterfactual import generate_counterfactuals
from core.action import decide_action


# ----------------- FastAPI app -----------------
app = FastAPI(title="Job-Match Copilot API", version="beta-02")


# ----------------- Pydantic models -----------------
class Resume(BaseModel):
    summary: Optional[str] = None
    skills: List[str] = []
    experience_bullets: List[str] = []
    projects: List[str] = []
    education: List[str] = []
    courses: List[str] = []


class Job(BaseModel):
    title: Optional[str] = None
    requirements: List[str] = []
    preferred: List[str] = []


class ScoreRequest(BaseModel):
    # Either provide structured objects...
    resume: Optional[Resume] = None
    job: Optional[Job] = None
    # ...or file paths the backend can read
    resume_path: Optional[str] = None
    job_path: Optional[str] = None
    # Optional explicit lists (UI may send these)
    requirements: Optional[List[str]] = None
    preferred: Optional[List[str]] = None


# ----------------- Helpers to resolve inputs -----------------
def _resolve_resume(req: ScoreRequest) -> Dict:
    """
    Return a dict resume with sectionized fields expected by downstream logic.
    Order of precedence:
      1) req.resume (already structured)
      2) req.resume_path -> parse_resume(path)
    """
    if req.resume:
        return req.resume.model_dump()
    if req.resume_path:
        # parse_resume should read file and return a dict with the same keys as Resume
        return parse_resume(req.resume_path)
    raise HTTPException(status_code=422, detail="Provide resume or resume_path")


def _resolve_job(req: ScoreRequest) -> Dict:
    """
    Return a dict job with 'requirements' and 'preferred' lists.
    Order of precedence:
      1) req.job (already structured)
      2) req.job_path -> parse_job(path)
    If explicit req.requirements / req.preferred are provided, they override/augment.
    """
    if req.job:
        job = req.job.model_dump()
    elif req.job_path:
        job = parse_job(req.job_path)
    else:
        raise HTTPException(status_code=422, detail="Provide job or job_path")

    # If the client sent explicit lists, prefer them (they’re already sectionized by UI)
    if req.requirements is not None:
        job["requirements"] = req.requirements
    if req.preferred is not None:
        job["preferred"] = req.preferred
    # Ensure keys exist
    job.setdefault("requirements", [])
    job.setdefault("preferred", [])
    return job


@app.get("/", include_in_schema=False)
def root():
    # simple friendly landing page (200 OK)
    return JSONResponse(
        {"service": "Job-Match Copilot API", "status": "ok", "docs": "/docs", "health": "/healthz"}
    )

@app.head("/", include_in_schema=False)
def root_head():
    # some providers send HEAD; return 200 too
    return PlainTextResponse("", status_code=200)
# ----------------- Health -----------------
@app.get("/healthz")
def healthz():
    return {"ok": True}


# ----------------- Score -----------------
@app.post("/score")
def score_match(request: ScoreRequest = Body(...)):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)

        evals = evaluate_requirements(
            job.get("requirements") or [],
            resume,
            preferred=job.get("preferred") or [],
        )
        agg = compute_match_score(evals)
        return {**agg, "evaluations": evals}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/score failed: {e}")


# ----------------- Counterfactual -----------------
@app.post("/counterfactual")
def counterfactual(request: ScoreRequest = Body(...)):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        suggestions = generate_counterfactuals(resume, job)
        return {"suggestions": suggestions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/counterfactual failed: {e}")


# ----------------- Action -----------------
@app.post("/action")
def action(request: ScoreRequest = Body(...)):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        evals = evaluate_requirements(
            job.get("requirements") or [],
            resume,
            preferred=job.get("preferred") or [],
        )
        decision = decide_action(evals)
        return decision
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/action failed: {e}")
