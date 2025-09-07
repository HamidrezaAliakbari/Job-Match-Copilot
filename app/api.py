"""FastAPI application for the Job-Match Copilot demo."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

app = FastAPI(title="Job-Match Copilot API", version="beta-02")

# CORS: wide-open for bring-up; lock to your UI origin after deploy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # e.g., ["https://<your-ui>.onrender.com"] later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok", "version": "beta-02"}

# ------------------------- Helpers ------------------------

def _load_resume(req: ScoreRequest) -> Dict[str, Any]:
    """Accept pre-parsed dict OR raw text OR file path."""
    if req.resume is not None:
        return req.resume
    if getattr(req, "resume_text", None):
        return parse_resume(text=req.resume_text)
    if req.resume_path:
        return parse_resume(path=req.resume_path)
    raise HTTPException(status_code=422, detail="Provide resume/resume_text or resume_path")

def _load_job(req: ScoreRequest) -> Dict[str, Any]:
    """Accept pre-parsed dict OR raw text OR file path OR bare requirements."""
    if req.job is not None:
        return req.job
    if getattr(req, "job_text", None):
        return parse_job(text=req.job_text, requirements=req.requirements, preferred=req.preferred)
    if req.job_path:
        return parse_job(path=req.job_path, requirements=req.requirements, preferred=req.preferred)
    if req.requirements:
        return {"title": "Job", "requirements": req.requirements, "preferred": req.preferred or []}
    raise HTTPException(status_code=422, detail="Provide job/job_text/job_path or requirements")

def _normalize_token(s: str) -> str:
    return s.casefold().replace("-", " ").strip()

def _has_requirement(resume: Dict[str, Any], req: str) -> Tuple[bool, Optional[str]]:
    needle = _normalize_token(req)
    for sk in resume.get("skills", []) or []:
        if _normalize_token(sk) == needle:
            return True, sk
    raw = (resume.get("raw_text") or "").strip()
    if needle and _normalize_token(raw).find(needle) != -1:
        return True, req
    return False, None

def _normalize_evaluations(evals_in: List[Dict[str, Any]], resume: Dict[str, Any]) -> List[RequirementResult]:
    out: List[RequirementResult] = []
    for ev in evals_in or []:
        req_name = ev.get("requirement") or ev.get("name") or ev.get("req") or ""
        met = (
            ev.get("met")
            if "met" in ev
            else (bool(ev.get("match")) if "match" in ev else (str(ev.get("status", "")).lower() == "met"))
        )
        evidence = ev.get("evidence")
        if isinstance(evidence, list):
            evidence = "; ".join(str(x) for x in evidence)
        confidence = ev.get("confidence")

        if met is False:
            ok, ev_str = _has_requirement(resume, req_name)
            if ok:
                met = True
                try:
                    c = float(confidence) if confidence is not None else 0.0
                except Exception:
                    c = 0.0
                confidence = max(c, 0.6)
                if not evidence:
                    evidence = ev_str or req_name

        out.append(
            RequirementResult(
                requirement=str(req_name),
                met=bool(met),
                evidence=(evidence if (evidence is None or isinstance(evidence, str)) else str(evidence)),
                confidence=(float(confidence) if confidence is not None else None),
            )
        )
    return out

# -------------------------- Routes ------------------------

@app.post("/score", response_model=ScoreResponse)
def score_match(request: ScoreRequest) -> ScoreResponse:
    resume = _load_resume(request)
    job = _load_job(request)

    requirements = job.get("requirements") or []
    if not requirements:
        raise HTTPException(status_code=422, detail="No requirements provided")

    evaluations = evaluate_requirements(requirements, resume)
    eval_models = _normalize_evaluations(evaluations, resume)
    score_dict = compute_match_score(evaluations)

    return ScoreResponse(
        score=float(score_dict["score"]),
        confidence=float(score_dict["confidence"]),
        evaluations=eval_models,
    )

@app.post("/counterfactual", response_model=CounterfactualResponse)
def counterfactual(request: ScoreRequest) -> CounterfactualResponse:
    resume = _load_resume(request)
    job = _load_job(request)
    evaluations = evaluate_requirements(job.get("requirements", []), resume)
    suggestions = generate_counterfactuals(evaluations, resume)
    if suggestions and not isinstance(suggestions[0], str):
        suggestions = [str(s) for s in suggestions]
    return CounterfactualResponse(suggestions=suggestions)

@app.post("/action", response_model=ActionResponse)
def action_recommendation(request: ScoreRequest) -> ActionResponse:
    resume = _load_resume(request)
    job = _load_job(request)
    evaluations = evaluate_requirements(job.get("requirements", []), resume)
    score_dict = compute_match_score(evaluations)
    suggestions = generate_counterfactuals(evaluations, resume)
    action = decide_action(score_dict["score"], score_dict["confidence"], suggestions)
    if "decision" in action and "details" in action:
        action = {"action": action["decision"], "rationale": str(action["details"])}
    return ActionResponse(**action)
