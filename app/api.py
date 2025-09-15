# app/api.py
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from core.parse_resume import parse_resume
from core.parse_job import parse_job
from core.reason_llm import evaluate_requirements
from core.score import compute_match_score
from core.counterfactual import generate_counterfactuals  # your existing file
from core.policy import decide_action
from .schemas import (
    ScoreRequest, ScoreResponse, RequirementResult,
    CounterfactualResponse, ActionResponse
)

app = FastAPI(title="Job-Match Copilot API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
def root():
    return {"ok": True, "service": "job-match-copilot-api", "docs": "/docs", "health": "/healthz"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

def _resolve_resume(req: ScoreRequest) -> dict:
    if req.resume:
        return req.resume.dict()
    return parse_resume(req.resume_path, text=req.resume_text)

def _resolve_job(req: ScoreRequest) -> dict:
    if req.job:
        job = req.job.dict()
        return {
            "title": job.get("title") or "Job",
            "requirements": job.get("requirements") or [],
            "preferred": job.get("preferred") or [],
            "sections": {
                "minimum_qualifications": job.get("requirements") or [],
                "preferred_qualifications": job.get("preferred") or [],
                "responsibilities": [],
                "about": [],
                "other": [],
            },
        }
    return parse_job(req.job_path, text=req.job_text, requirements=req.requirements, preferred=req.preferred)

@app.post("/score", response_model=ScoreResponse)
def score_match(request: ScoreRequest) -> ScoreResponse:
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"File not found: {e}")

    evaluations = evaluate_requirements(job["requirements"], resume, preferred=job.get("preferred", []))
    eval_models = [RequirementResult(**ev) for ev in evaluations]
    score_dict = compute_match_score(evaluations)
    return ScoreResponse(score=score_dict["score"], confidence=score_dict["confidence"], evaluations=eval_models)

@app.post("/counterfactual", response_model=CounterfactualResponse)
def counterfactual(request: ScoreRequest) -> CounterfactualResponse:
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"File not found: {e}")

    evaluations = evaluate_requirements(job["requirements"], resume, preferred=job.get("preferred", []))
    suggestions = generate_counterfactuals(evaluations, resume)
    return CounterfactualResponse(suggestions=suggestions)

@app.post("/action", response_model=ActionResponse)
def action_recommendation(request: ScoreRequest) -> ActionResponse:
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"File not found: {e}")

    evaluations = evaluate_requirements(job["requirements"], resume, preferred=job.get("preferred", []))
    score_dict = compute_match_score(evaluations)
    suggestions = generate_counterfactuals(evaluations, resume)
    decision = decide_action(score_dict["score"], score_dict["confidence"], suggestions)
    return ActionResponse(**decision)
