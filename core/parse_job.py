from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import os
import re

# Recognize common section headers
HEADER_PATTERNS = [
    r"\bjob\s*title\b",
    r"\babout\s+(the\s+)?(role|job|team|company)\b",
    r"\boverview\b",
    r"\bdescription\b",
    r"\bresponsibilit(y|ies)\b",
    r"\bduties\b",
    r"\bminimum\s+qualifications?\b",
    r"\bbasic\s+qualifications?\b",
    r"\bpreferred\s+qualifications?\b",
    r"\bnice\s*to\s*have\b",
    r"\brequirements?\b",
]

HEADER_RE = re.compile(r"^\s*(?:{})(:)?\s*$".format("|".join(HEADER_PATTERNS)), re.I)
BULLET_RE = re.compile(r"^\s*(?:[-*•–]|(\d+[\.\)]))\s+(.*)$")

def _read_text(path: Optional[str], text: Optional[str]) -> str:
    if text and text.strip():
        return text
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Job file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    raise FileNotFoundError("Provide job_text or job_path")

def _normalize_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _is_header(line: str) -> bool:
    return bool(HEADER_RE.match(line.strip()))

def _collect_bullets(lines: List[str], start_idx: int) -> Tuple[List[str], int]:
    """Collect consecutive bullets starting at start_idx (exclusive), return bullets and index of next header."""
    out: List[str] = []
    i = start_idx + 1
    while i < len(lines):
        raw = lines[i].rstrip()
        if not raw.strip():
            i += 1
            continue
        if _is_header(raw):
            break
        m = BULLET_RE.match(raw)
        if m:
            item = m.group(2) or m.group(0)
            out.append(_normalize_line(item))
        else:
            # treat short, non-header lines as paragraph bullet continuations
            if len(raw) <= 280:
                out.append(_normalize_line(raw))
        i += 1
    # De-dup and trim
    dedup: List[str] = []
    seen = set()
    for x in out:
        k = x.lower()
        if k and k not in seen:
            seen.add(k)
            dedup.append(x)
    return dedup, i

def _extract_sections(job_text: str) -> Dict[str, List[str]]:
    """
    Returns dict with keys:
      - 'minimum' : bullets under Minimum/Basic Qualifications
      - 'preferred': bullets under Preferred/Nice to have
      - 'other': bullets found elsewhere (Responsibilities etc.)
    """
    lines = [ln.rstrip() for ln in job_text.splitlines()]
    minimum: List[str] = []
    preferred: List[str] = []
    other: List[str] = []

    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if _is_header(ln):
            hdr = ln.strip().lower().rstrip(":")
            bullets, j = _collect_bullets(lines, i)
            if "preferred" in hdr or "nice" in hdr:
                preferred.extend(bullets)
            elif "minimum" in hdr or "basic" in hdr:
                minimum.extend(bullets)
            else:
                other.extend(bullets)
            i = j
        else:
            # stand-alone bullets outside headers go to 'other'
            m = BULLET_RE.match(ln)
            if m:
                other.append(_normalize_line(m.group(2) or m.group(0)))
            i += 1

    # final tidy
    def _clean(L: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for x in L:
            y = _normalize_line(x)
            if not y: 
                continue
            if _is_header(y):  # protect against stray headers
                continue
            k = y.lower()
            if 2 <= len(y) <= 300 and k not in seen:
                seen.add(k)
                out.append(y)
        return out[:50]

    return {
        "minimum": _clean(minimum),
        "preferred": _clean(preferred),
        "other": _clean(other),
    }

def parse_job(job_path: Optional[str] = None,
              text: Optional[str] = None,
              requirements: Optional[List[str]] = None,
              preferred: Optional[List[str]] = None) -> Dict:
    """
    If explicit requirements/preferred are passed, use them.
    Else, extract from text into minimum/preferred/other and use:
      requirements := minimum or (minimum + other if minimum empty)
      preferred    := preferred
    """
    job_text = _read_text(job_path, text)

    if requirements is not None or preferred is not None:
        return {
            "title": "Job",
            "requirements": [r for r in (requirements or []) if r.strip() and not _is_header(r)],
            "preferred": [p for p in (preferred or []) if p.strip() and not _is_header(p)],
            "raw_text": job_text,
        }

    sections = _extract_sections(job_text)
    reqs = sections["minimum"] or (sections["minimum"] + sections["other"])
    prefs = sections["preferred"]

    return {
        "title": "Job",
        "requirements": reqs,
        "preferred": prefs,
        "raw_text": job_text,
    }
