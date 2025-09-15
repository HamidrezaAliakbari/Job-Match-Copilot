# core/parse_job.py
from __future__ import annotations
from typing import Dict, Optional, List
from pathlib import Path

from core.sectionizer import sectionize_job_text

def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")

def parse_job(path: Optional[str] = None,
              text: Optional[str] = None,
              requirements: Optional[List[str]] = None,
              preferred: Optional[List[str]] = None) -> Dict:
    """
    Return a normalized job object with keys:
      title(str), requirements[List[str]], preferred[List[str]]
    - If explicit requirements/preferred are provided, they take precedence.
    - Otherwise, we parse the raw JD and extract Minimum vs Preferred blocks.
    """
    if requirements or preferred:
        return sectionize_job_text(
            text or "",
            explicit_requirements=requirements,
            explicit_preferred=preferred,
        )

    if text and text.strip():
        return sectionize_job_text(text)

    if path:
        raw = _read(path)
        return sectionize_job_text(raw)

    return {"title": "", "requirements": [], "preferred": []}
