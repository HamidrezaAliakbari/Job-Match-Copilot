# app/schemas.py
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ResumeObj(BaseModel):
    skills: List[str] = []
    experience_bullets: List[str] = []
    projects: List[str] = []
    education: List[str] = []
    courses: List[str] = []

class JobObj(BaseModel):
    title: str = "Job"
    requirements: List[str] = []
    preferred: List[str] = []

class ScoreRequest(BaseModel):
    # Either provide raw objects
    resume: Optional[ResumeObj] = None
    job: Optional[JobObj] = None

    # Or provide file paths
    resume_path: Optional[str] = None
    job_path: Optional[str] = None

    # Or provide pasted text
    resume_text: Optional[str] = None
    job_text: Optional[str] = None

    # Optional overrides
    requirements: Optional[List[str]] = None
    preferred: Optional[List[str]] = None

class RequirementResult(BaseModel):
    requirement: str
    status: str
    evidence: List[str] = []
    bucket: str = "minimum"

class ScoreResponse(BaseModel):
    score: float
    confidence: float
    evaluations: List[RequirementResult]

class CounterfactualResponse(BaseModel):
    suggestions: List[Any] | Dict[str, Any]  # keep flexible for your current impl

class ActionResponse(BaseModel):
    action: str
    rationale: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
