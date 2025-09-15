# app/api.py
from __future__ import annotations
import os, traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.parse_resume import parse_resume
from core.parse_job import parse_job
from core.reason_llm import evaluate_requirements
from core.score import compute_match_score
from core.counterfactual import generate_counterfactuals
from core.policy import decide_action

from .schemas import (
    ScoreRequest,
    ScoreResponse,
    CounterfactualResponse,
    ActionResponse,
    RequirementResult,
)

app = FastAPI(title="Job-Match Copilot API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

SHOW_TRACEBACK = os.environ.get("SHOW_TRACEBACK", "0") == "1"
def _safe_error(detail: str, status_code: int = 400, exc: Exception | None = None):
    payload = {"detail": detail}
    if exc and SHOW_TRACEBACK:
        payload["traceback"] = traceback.format_exc()
    return JSONResponse(payload, status_code=status_code)

@app.post("/score", response_model=ScoreResponse)
def score_match(request: ScoreRequest) -> ScoreResponse:
    try:
        resume = parse_resume(
            path=getattr(request, "resume_path", None),
            text=getattr(request, "resume_text", None),
            obj=getattr(request, "resume", None),
        )
        job = parse_job(
            path=getattr(request, "job_path", None),
            job_text=getattr(request, "job_text", None),
            requirements=getattr(request, "requirements", None),
            preferred=getattr(request, "preferred", None),
            obj=getattr(request, "job", None),
        )

        if not job.get("requirements"):
            return _safe_error("No job requirements were extracted or provided.", 422)

        evaluations = evaluate_requirements(job["requirements"], resume)
        eval_models = [RequirementResult(**ev) for ev in evaluations]
        score_dict = compute_match_score(evaluations)
        return ScoreResponse(
            score=score_dict["score"],
            confidence=score_dict["confidence"],
            evaluations=eval_models,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return _safe_error("Unhandled error in /score", 500, e)

@app.post("/counterfactual", response_model=CounterfactualResponse)
def counterfactual(request: ScoreRequest) -> CounterfactualResponse:
    try:
        resume = parse_resume(
            path=getattr(request, "resume_path", None),
            text=getattr(request, "resume_text", None),
            obj=getattr(request, "resume", None),
        )
        job = parse_job(
            path=getattr(request, "job_path", None),
            job_text=getattr(request, "job_text", None),
            requirements=getattr(request, "requirements", None),
            preferred=getattr(request, "preferred", None),
            obj=getattr(request, "job", None),
        )
        evaluations = evaluate_requirements(job["requirements"], resume)
        suggestions = generate_counterfactuals(evaluations, resume)
        return CounterfactualResponse(suggestions=suggestions)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return _safe_error("Unhandled error in /counterfactual", 500, e)

@app.post("/action", response_model=ActionResponse)
def action_recommendation(request: ScoreRequest) -> ActionResponse:
    try:
        resume = parse_resume(
            path=getattr(request, "resume_path", None),
            text=getattr(request, "resume_text", None),
            obj=getattr(request, "resume", None),
        )
        job = parse_job(
            path=getattr(request, "job_path", None),
            job_text=getattr(request, "job_text", None),
            requirements=getattr(request, "requirements", None),
            preferred=getattr(request, "preferred", None),
            obj=getattr(request, "job", None),
        )
        evaluations = evaluate_requirements(job["requirements"], resume)
        score_dict = compute_match_score(evaluations)
        suggestions = generate_counterfactuals(evaluations, resume)
        action = decide_action(score_dict["score"], score_dict["confidence"], suggestions)
        return ActionResponse(**action)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return _safe_error("Unhandled error in /action", 500, e)
