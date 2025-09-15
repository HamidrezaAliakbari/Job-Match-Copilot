# core/parse_resume.py
from __future__ import annotations
from typing import Dict, Optional
from pathlib import Path

from core.sectionizer import sectionize_resume_text

def _read(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8", errors="ignore")

def parse_resume(path: Optional[str] = None, text: Optional[str] = None) -> Dict:
    """
    Return a normalized resume object with keys:
      summary(str), skills[List[str]], experience_bullets[List[str]],
      projects[List[str]], education[List[str]], courses[List[str]]
    """
    if text and text.strip():
        return sectionize_resume_text(text)

    if path:
        raw = _read(path)
        return sectionize_resume_text(raw)

    # empty fallback
    return {
        "summary": "",
        "skills": [],
        "experience_bullets": [],
        "projects": [],
        "education": [],
        "courses": [],
    }
