# app/schemas.py
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RequirementResult(BaseModel):
    requirement: str
    status: str                   # "Met" | "Partially met" | "Missing"
    evidence: Optional[List[str]] = None
    confidence: Optional[float] = None
    section: Optional[str] = None

class ScoreRequest(BaseModel):
    # EITHER pass raw text…
    resume_text: Optional[str] = Field(None, description="Raw resume text")
    job_text: Optional[str] = Field(None, description="Raw job description text")

    # …OR pass file paths that exist on the API container (usually not in cloud)
    resume_path: Optional[str] = None
    job_path: Optional[str] = None

    # (Optional) if you already extracted structured dicts (not required)
    resume: Optional[Dict[str, Any]] = None
    job: Optional[Dict[str, Any]] = None

    # Optional hints
    requirements: Optional[List[str]] = None
    preferred: Optional[List[str]] = None

class ScoreResponse(BaseModel):
    score: float
    confidence: float
    evaluations: List[RequirementResult]

class CounterfactualResponse(BaseModel):
    suggestions: Any  # section-wise dict or list

class ActionResponse(BaseModel):
    action: str
    rationale: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
