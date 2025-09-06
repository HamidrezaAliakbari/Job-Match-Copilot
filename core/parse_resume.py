from __future__ import annotations
from typing import Dict, List
import re

def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]

def _sectionize(lines: List[str]) -> dict:
    sec_map = {"skills": [], "experience": [], "education": [], "projects": [], "other": []}
    cur = "other"
    for ln in lines:
        low = ln.lower()
        if "skill" in low: cur = "skills"; continue
        if "experience" in low or "work" in low: cur = "experience"; continue
        if "education" in low: cur = "education"; continue
        if "project" in low: cur = "projects"; continue
        sec_map.setdefault(cur, []).append(ln)
    return sec_map

def _extract_skills(skill_lines: List[str]) -> List[str]:
    skills = []
    for ln in skill_lines:
        parts = re.split(r"[•,;/\|]|\t|\s{2,}", ln)
        for p in parts:
            t = p.strip()
            if t and len(t) <= 40:
                skills.append(t)
    seen, out = set(), []
    for s in skills:
        if s.lower() not in seen:
            seen.add(s.lower()); out.append(s)
    return out[:128]

def parse_resume(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = _split_lines(text)
    secs = _sectionize(lines)
    return {
        "raw_text": text,
        "skills": _extract_skills(secs.get("skills", [])),
        "experience_bullets": secs.get("experience", []),
        "projects": secs.get("projects", []),
        "education": secs.get("education", []),
    }
