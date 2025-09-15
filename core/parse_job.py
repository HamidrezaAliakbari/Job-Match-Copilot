# core/parse_job.py
from __future__ import annotations
from typing import Dict, List, Optional, Any
import os
import re

HEADER_STOPWORDS = {
    "about the job", "responsibilities", "what you’ll do", "what you will do",
    "minimum qualifications", "basic qualifications", "must have", "must-haves",
    "preferred qualifications", "nice to have", "nice-to-have",
    "requirements", "required", "who you are", "qualifications",
    "benefits", "compensation", "about us", "about you", "location",
    "preferred", "role", "summary", "overview", "job description",
    "principal duties and responsibilities", "research professional 1:",
    "research professional 2:", "duties", "preferred qualifications:"
}

BULLET_RE = re.compile(r"^\s*([\-*•–]|(\d+[\.\)]))\s+")
HEADER_LIKE_RE = re.compile(r"^\s*([A-Za-z].{0,60}):\s*$")  # lines ending with ':'

def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _looks_like_header(line: str) -> bool:
    s = line.strip().strip(": ").lower()
    if not s:
        return False
    if s in HEADER_STOPWORDS:
        return True
    if HEADER_LIKE_RE.match(line):
        return True
    # very short single-phrase lines are often headers
    if len(s.split()) <= 5 and not any(ch.isdigit() for ch in s):
        return True
    return False

def _split_lines_keep_bullets(text: str) -> List[str]:
    out: List[str] = []
    for ln in text.splitlines():
        t = ln.strip()
        if not t:
            continue
        out.append(t)
    return out

def _extract_requirement_lines(text: str, max_items: int = 50) -> List[str]:
    """
    Extract plausible requirement lines:
      - keep bullet/numbered lines
      - allow non-bullets if shortish and not headers
      - drop lines that look like pure section headers
    """
    lines = _split_lines_keep_bullets(text)
    items: List[str] = []
    for ln in lines:
        # skip obvious headers
        if _looks_like_header(ln):
            continue
        if BULLET_RE.match(ln):
            items.append(ln)
            continue
        # heuristically allow short actionable lines
        if 2 <= len(ln) <= 240 and any(ch.isalpha() for ch in ln):
            items.append(ln)
        if len(items) >= max_items:
            break
    # strip bullets/markers and clean
    cleaned: List[str] = []
    for it in items:
        it = BULLET_RE.sub("", it).strip(" •*-–\t")
        if it and not _looks_like_header(it):
            cleaned.append(it)
    return cleaned

def parse_job(
    path: Optional[str] = None,
    job_text: Optional[str] = None,
    requirements: Optional[List[str]] = None,
    preferred: Optional[List[str]] = None,
    obj: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Flexible job loader:
      - If 'obj' provided, normalize and return
      - Else if 'job_text' provided, extract requirement lines
      - Else if 'path' provided, read file then extract
      - 'requirements' and 'preferred' arrays, if provided, override/augment
    Returns: {title, requirements, preferred}
    """
    if obj and not isinstance(obj, dict):
        raise ValueError("job 'obj' must be a dict if provided")

    if obj:
        title = str(obj.get("title") or "Job").strip() or "Job"
        reqs = [str(x).strip() for x in (obj.get("requirements") or []) if str(x).strip()]
        prefs= [str(x).strip() for x in (obj.get("preferred") or []) if str(x).strip()]
        return {"title": title, "requirements": reqs, "preferred": prefs}

    raw = job_text
    if (raw is None or not str(raw).strip()) and path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Job file not found: {path}")
        raw = _read_text_file(path)

    raw = (raw or "").strip()
    title = "Job"

    # Start from extracted requirements if we have raw text
    extracted = _extract_requirement_lines(raw) if raw else []

    # Overlay explicit arrays if provided
    if requirements:
        extracted = [str(x).strip() for x in requirements if str(x).strip()] or extracted

    prefs = [str(x).strip() for x in (preferred or []) if str(x).strip()]

    # Final guard: ensure we don't return pure headers as requirements
    extracted = [x for x in extracted if not _looks_like_header(x)]

    # Fallback: if nothing extracted, use whole text trimmed once
    if not extracted and raw:
        extracted = [raw[:500]]

    return {"title": title, "requirements": extracted, "preferred": prefs}
