from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ScoreRequest(BaseModel):
    # Option A: direct dicts
    resume: Optional[Dict[str, Any]] = None
    job: Optional[Dict[str, Any]] = None
    # Option B: file paths
    resume_path: Optional[str] = None
    job_path: Optional[str] = None
    # Option C: direct requirement lists
    requirements: Optional[List[str]] = None
    preferred: Optional[List[str]] = None

class RequirementResult(BaseModel):
    requirement: str
    status: str
    evidence: List[str] = Field(default_factory=list)

class ScoreResponse(BaseModel):
    score: float
    confidence: float
    evaluations: List[RequirementResult]

class CounterfactualResponse(BaseModel):
    suggestions: List[Dict[str, Any]]

class ActionResponse(BaseModel):
    decision: str
    details: Dict[str, Any] = Field(default_factory=dict)
