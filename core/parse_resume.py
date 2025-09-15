# core/parse_resume.py
from __future__ import annotations
from typing import Dict, List, Optional, Any
import os

def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _normalize_list(x: Any) -> List[str]:
    if not x:
        return []
    if isinstance(x, (list, tuple)):
        return [str(i).strip() for i in x if str(i).strip()]
    return [str(x).strip()]

def parse_resume(
    path: Optional[str] = None,
    text: Optional[str] = None,
    obj: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Flexible resume loader:
      - If 'obj' provided, normalize and return
      - Else if 'text' provided, create a minimal resume object
      - Else if 'path' provided, read file and create minimal object
    Always returns:
      {skills, experience_bullets, projects, education, courses}
    """
    if obj and not isinstance(obj, dict):
        raise ValueError("resume 'obj' must be a dict if provided")

    if obj:
        skills = _normalize_list(obj.get("skills"))
        exp    = _normalize_list(obj.get("experience_bullets"))
        projs  = _normalize_list(obj.get("projects"))
        edu    = _normalize_list(obj.get("education"))
        courses= _normalize_list(obj.get("courses"))
        return {
            "skills": skills,
            "experience_bullets": exp,
            "projects": projs,
            "education": edu,
            "courses": courses,
        }

    raw = text
    if (raw is None or not str(raw).strip()) and path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Resume file not found: {path}")
        raw = _read_text_file(path)

    raw = (raw or "").strip()
    # Minimal, safe defaults if only raw text available
    return {
        "skills": [],
        "experience_bullets": [raw] if raw else [],
        "projects": [],
        "education": [],
        "courses": [],
    }
