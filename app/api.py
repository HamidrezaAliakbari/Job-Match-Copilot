# app/api.py
"""FastAPI application for the Job-Match Copilot demo."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from core.parse_resume import parse_resume
from core.parse_job import parse_job
from core.reason_llm import evaluate_requirements
from core.score import compute_match_score
from core.policy import decide_action
from core import counterfactual as cf  # robust import; see alias inside module

from .schemas import (
    ScoreRequest, ScoreResponse,
    CounterfactualResponse, ActionResponse,
    RequirementResult,
)




app = FastAPI(title="Job-Match Copilot API", version="beta-02")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")                # <-- returns 200 OK
def root():
    return {"ok": True}

@app.get("/healthz")         # <-- returns 200 OK
def healthz():
    return {"status": "ok"}

@app.post("/score", response_model=ScoreResponse)
def score_match(request: ScoreRequest) -> ScoreResponse:
    try:
        # accept either path or raw text (your parsers should handle both)
        resume = parse_resume(request.resume_path, text=getattr(request, "resume_text", None))
        job = parse_job(
            request.job_path,
            text=getattr(request, "job_text", None),
            requirements=request.requirements,
            preferred=request.preferred,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    evaluations = evaluate_requirements(job["requirements"], resume)
    eval_models = [RequirementResult(**ev) for ev in evaluations]
    score_dict = compute_match_score(evaluations)
    return ScoreResponse(score=score_dict["score"], confidence=score_dict["confidence"], evaluations=eval_models)

@app.post("/counterfactual", response_model=CounterfactualResponse)
def counterfactual(request: ScoreRequest) -> CounterfactualResponse:
    try:
        resume = parse_resume(request.resume_path, text=getattr(request, "resume_text", None))
        job = parse_job(
            request.job_path,
            text=getattr(request, "job_text", None),
            requirements=request.requirements,
            preferred=request.preferred,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    evaluations = evaluate_requirements(job["requirements"], resume)
    suggestions = cf.generate_counterfactuals(evaluations, resume)  # alias inside module ensures function exists
    return CounterfactualResponse(suggestions=suggestions)

@app.post("/action", response_model=ActionResponse)
def action_recommendation(request: ScoreRequest) -> ActionResponse:
    try:
        resume = parse_resume(request.resume_path, text=getattr(request, "resume_text", None))
        job = parse_job(
            request.job_path,
            text=getattr(request, "job_text", None),
            requirements=request.requirements,
            preferred=request.preferred,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    evaluations = evaluate_requirements(job["requirements"], resume)
    score_dict = compute_match_score(evaluations)
    suggestions = cf.generate_counterfactuals(evaluations, resume)
    action = decide_action(score_dict["score"], score_dict["confidence"], suggestions)
    return ActionResponse(**action)
