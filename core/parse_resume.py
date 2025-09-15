from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import os
import re

SECTION_HEADERS = [
    r"professional\s+summary",
    r"summary",
    r"experience",
    r"work\s+experience",
    r"projects?",
    r"education",
    r"skills?",
    r"courses?",
    r"certifications?",
    r"publications?",
]

SEC_RE = re.compile(r"^\s*(?:{})(:)?\s*$".format("|".join(SECTION_HEADERS)), re.I)
BULLET_RE = re.compile(r"^\s*(?:[-*•–]|(\d+[\.\)]))\s+(.*)$")

def _read_text(path: Optional[str], text: Optional[str]) -> str:
    if text and text.strip():
        return text
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Resume file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError("Provide resume_text or resume_path")

def _is_section_title(line: str) -> bool:
    return bool(SEC_RE.match(line.strip()))

def _normalize_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _collect_until_next_section(lines: List[str], start_idx: int) -> Tuple[List[str], int]:
    """Return lines after a section header up to (but not including) the next header."""
    buf: List[str] = []
    i = start_idx + 1
    while i < len(lines):
        raw = lines[i].rstrip()
        if _is_section_title(raw):
            break
        if raw.strip():
            buf.append(raw)
        i += 1
    return buf, i

def _extract_bullets(block: List[str]) -> List[str]:
    items: List[str] = []
    for raw in block:
        m = BULLET_RE.match(raw)
        if m:
            items.append(_normalize_line(m.group(2) or m.group(0)))
        else:
            # accept short lines as bullets too
            if 2 <= len(raw) <= 300:
                items.append(_normalize_line(raw))
    # strip accidental section titles from bullets
    items = [x for x in items if not _is_section_title(x)]
    # de-dup
    seen = set()
    out: List[str] = []
    for x in items:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out[:100]

def parse_resume(resume_path: Optional[str] = None, text: Optional[str] = None) -> Dict:
    """
    Returns a normalized resume dict:
      {
        summary: str,
        skills: List[str],
        experience_bullets: List[str],
        projects: List[str],
        education: List[str],
        courses: List[str]
      }
    """
    raw = _read_text(resume_path, text)
    lines = [ln.rstrip() for ln in raw.splitlines()]

    # find sections
    sections: Dict[str, List[str]] = {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _is_section_title(ln):
            hdr = ln.strip().lower().rstrip(":")
            key = re.sub(r"\s+", " ", hdr)
            block, j = _collect_until_next_section(lines, i)
            sections[key] = block
            i = j
        else:
            i += 1

    # helper: get best matching section content by any header alias
    def get_sec(*aliases: str) -> List[str]:
        for a in aliases:
            for k, v in sections.items():
                if re.fullmatch(a, k, flags=re.I):
                    return v
        return []

    # build fields
    summary_lines = get_sec(r"professional\s+summary", r"summary")
    experience_lines = get_sec(r"experience", r"work\s+experience")
    projects_lines = get_sec(r"projects?")
    education_lines = get_sec(r"education")
    skills_lines = get_sec(r"skills?")
    courses_lines = get_sec(r"courses?")

    summary = _normalize_line(" ".join(summary_lines)) if summary_lines else ""

    # crude skill extractor from skills_lines (comma/semicolon/pipe separated)
    skills: List[str] = []
    for ln in skills_lines[:8]:
        parts = re.split(r"[,\u2022;|/]+", ln)
        for p in parts:
            t = p.strip()
            if 1 < len(t) <= 40 and any(ch.isalpha() for ch in t):
                if not re.fullmatch(r"and|or|etc\.?", t, flags=re.I):
                    skills.append(t)
    # de-dup
    seen = set()
    skills_out: List[str] = []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            skills_out.append(s)

    return {
        "summary": summary,
        "skills": skills_out[:25],
        "experience_bullets": _extract_bullets(experience_lines),
        "projects": _extract_bullets(projects_lines),
        "education": _extract_bullets(education_lines),
        "courses": _extract_bullets(courses_lines),
    }
