# core/parse_resume.py
from __future__ import annotations
import os
from typing import Dict, List, Optional
import re

# If you already have core/sectionizer.py, we’ll try to use it; else fallback.
try:
    from .sectionizer import sectionize_text  # type: ignore
except Exception:
    sectionize_text = None  # fallback used

BULLET_RE = re.compile(r"^\s*(?:[-*•–]|(\d+[\.\)]))\s+")

def _read_text(path: Optional[str], text: Optional[str]) -> str:
    if text and text.strip():
        return text.strip()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    if path:
        raise FileNotFoundError(path)
    return ""

def _fallback_sections(txt: str) -> Dict[str, List[str]]:
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    # naive split into buckets by keyword
    buckets = {"summary": [], "skills": [], "experience": [], "projects": [], "education": [], "courses": []}
    current = "experience"
    for ln in lines:
        low = ln.lower().rstrip(":")
        if "summary" in low:
            current = "summary"; continue
        if "skill" in low:
            current = "skills"; continue
        if "project" in low:
            current = "projects"; continue
        if "education" in low:
            current = "education"; continue
        if "course" in low:
            current = "courses"; continue
        # bucket line
        if current in ("experience", "projects"):
            # split bullets and semicolons
            parts = re.split(r"[;•]", ln) if not BULLET_RE.match(ln) else [BULLET_RE.sub("", ln)]
            for p in parts:
                t = p.strip()
                if 2 <= len(t) <= 400:
                    buckets[current].append(t)
        else:
            buckets[current].append(ln)
    return buckets

def parse_resume(path: Optional[str] = None, *, text: Optional[str] = None) -> Dict:
    raw = _read_text(path, text)
    if not raw:
        return {"skills": [], "experience_bullets": [], "projects": [], "education": [], "courses": [], "summary": ""}

    if sectionize_text:
        sec = sectionize_text(raw)
    else:
        sec = _fallback_sections(raw)

    skills = []
    for ln in sec.get("skills", []):
        skills.extend([t.strip() for t in re.split(r"[,\u2022;|/]+", ln) if 1 < len(t.strip()) <= 40])
    # dedupe
    seen = set(); skills_d = []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k); skills_d.append(s)

    resume = {
        "summary": " ".join(sec.get("summary", [])[:3])[:600],
        "skills": skills_d[:50],
        "experience_bullets": sec.get("experience", [])[:100],
        "projects": sec.get("projects", [])[:50],
        "education": sec.get("education", [])[:20],
        "courses": sec.get("courses", [])[:50],
    }
    return resume
