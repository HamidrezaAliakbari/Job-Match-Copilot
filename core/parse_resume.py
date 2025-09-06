from __future__ import annotations
from typing import Dict, List
import re

SECTION_KEYS = {
    "summary": ["summary", "profile", "objective"],
    "skills": ["skills", "technical skills"],
    "experience": ["experience", "work experience", "professional experience", "employment"],
    "education": ["education", "academic"],
    "projects": ["projects", "personal projects", "research projects"],
}

def _split_lines(text: str) -> List[str]:
    return [ln.rstrip() for ln in text.splitlines()]

def _which_section(line_lower: str, current: str) -> str:
    for sec, keys in SECTION_KEYS.items():
        if any(k in line_lower for k in keys):
            return sec
    return current

def _extract_skills(skill_lines: List[str]) -> List[str]:
    skills = []
    for ln in skill_lines:
        parts = re.split(r"[•,;/\|]|\t|\s{2,}", ln)
        for p in parts:
            t = p.strip()
            if t and 1 < len(t) <= 40:
                skills.append(t)
    seen, out = set(), []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k); out.append(s)
    return out[:128]

def parse_resume(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = [ln for ln in _split_lines(raw) if ln.strip()]
    sections: Dict[str, List[str]] = {k: [] for k in SECTION_KEYS.keys()}
    sections.setdefault("other", [])

    current = "summary"  # default early lines are treated as summary until a header appears
    for ln in lines:
        low = ln.lower().strip()
        new_sec = _which_section(low, current)
        if new_sec != current:
            current = new_sec
            continue if_header := False
        # heuristically treat “header lines” as markers — we already switched section, skip line if it’s a header
        if any(low.startswith(k) for ks in SECTION_KEYS.values() for k in ks):
            continue
        sections.setdefault(current, []).append(ln)

    return {
        "raw_text": raw,
        "summary": " ".join(sections.get("summary", [])[:5]).strip(),
        "skills": _extract_skills(sections.get("skills", [])),
        "experience_bullets": [ln for ln in sections.get("experience", []) if ln.strip()][:256],
        "projects": [ln for ln in sections.get("projects", []) if ln.strip()][:128],
        "education": [ln for ln in sections.get("education", []) if ln.strip()][:64],
    }
