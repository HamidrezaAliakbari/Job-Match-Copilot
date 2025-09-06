"""FastAPI application for the Job-Match Copilot demo (section-wise counterfactuals)."""

from __future__ import annotations
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.parse_resume import parse_resume
from core.parse_job import parse_job
from core.reason_llm import evaluate_requirements
from core.score import compute_match_score
from core.counterfactual import generate_counterfactuals_by_section
from core.policy import decide_action

from .schemas import (
    ScoreRequest, ScoreResponse,
    CounterfactualResponse, ActionResponse,
    RequirementResult,
)

app = FastAPI(title="Job-Match Copilot API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}

def _load_resume(req: ScoreRequest) -> Dict[str, Any]:
    if req.resume is not None:
        return req.resume
    if req.resume_path:
        return parse_resume(req.resume_path)
    raise HTTPException(status_code=422, detail="Provide resume or resume_path")

def _load_job(req: ScoreRequest) -> Dict[str, Any]:
    if req.job is not None:
        return req.job
    if req.job_path:
        return parse_job(req.job_path, req.requirements, req.preferred)
    if req.requirements:
        return {"title": "Job", "requirements": req.requirements, "preferred": req.preferred or []}
    raise HTTPException(status_code=422, detail="Provide job, job_path, or requirements")

@app.post("/score", response_model=ScoreResponse)
def score_match(request: ScoreRequest) -> ScoreResponse:
    resume = _load_resume(request)
    job = _load_job(request)
    reqs = job.get("requirements", [])
    if not reqs:
        raise HTTPException(status_code=422, detail="No requirements provided")
    evaluations = evaluate_requirements(reqs, resume)
    eval_models = [RequirementResult(**ev) for ev in evaluations]
    score_dict = compute_match_score(evaluations)
    return ScoreResponse(score=score_dict["score"], confidence=score_dict["confidence"], evaluations=eval_models)

@app.post("/counterfactual", response_model=CounterfactualResponse)
def counterfactual(request: ScoreRequest) -> CounterfactualResponse:
    resume = _load_resume(request)
    job = _load_job(request)
    reqs = job.get("requirements", [])
    if not reqs:
        raise HTTPException(status_code=422, detail="No requirements provided")
    evaluations = evaluate_requirements(reqs, resume)

    sectioned, flat = generate_counterfactuals_by_section(evaluations, resume, job)
    return CounterfactualResponse(suggestions_by_section=sectioned, suggestions=flat)

@app.post("/action", response_model=ActionResponse)
def action_recommendation(request: ScoreRequest) -> ActionResponse:
    resume = _load_resume(request)
    job = _load_job(request)
    reqs = job.get("requirements", [])
    if not reqs:
        raise HTTPException(status_code=422, detail="No requirements provided")
    evaluations = evaluate_requirements(reqs, resume)
    score_dict = compute_match_score(evaluations)

    # We still use flat suggestions to inform action policy; sectioning is only UI/UX
    sectioned, flat = generate_counterfactuals_by_section(evaluations, resume, job)
    action = decide_action(score_dict["score"], score_dict["confidence"], flat)
    return ActionResponse(**action)
