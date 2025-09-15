# core/sectionizer.py
import re
from typing import Dict, List, Tuple

# Canonical section name map (normalize various header spellings to one key)
SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "profile", "objective"],
    "experience": ["experience", "work experience", "professional experience", "employment history"],
    "education": ["education", "academics"],
    "projects": ["projects", "selected projects"],
    "skills": ["skills", "technical skills", "core skills", "key skills"],
    "courses": ["courses", "relevant coursework", "coursework"],
    # JD-specific
    "minimum_qualifications": ["minimum qualifications", "basic qualifications", "required qualifications", "requirements"],
    "preferred_qualifications": ["preferred qualifications", "nice to have", "preferred", "bonus"],
    "responsibilities": ["responsibilities", "what you will do", "about the role"],
}

# Build detection regexes once
HEADER_PATTERNS = [
    re.compile(rf"^\s*({re.escape(alias)})\s*:?\s*$", re.IGNORECASE)
    for group in SECTION_ALIASES.values()
    for alias in group
]

# Broader job header detector (for one-liners like "Minimum Qualifications:" mixed in bullets)
JOB_SECTION_HEADER_RE = re.compile(
    r"^\s*(minimum|preferred|basic|required|about|responsibilit(?:y|ies)|qualifications?|skills?)\b.*:?$",
    re.IGNORECASE,
)

BULLET_RE = re.compile(r"^\s*([\-*•–]|(\d+\.)|(\d+\)))\s+")


def is_section_header(line: str) -> bool:
    """Return True if the line looks like a section header (resume or JD)."""
    s = (line or "").strip()
    if not s:
        return False
    if s.endswith(":"):
        # Obvious header
        return True
    # Exact header aliases
    for pat in HEADER_PATTERNS:
        if pat.match(s):
            return True
    # Broader JD header phrases (e.g., 'Minimum Qualifications:')
    if JOB_SECTION_HEADER_RE.match(s):
        return True
    # ALL CAPS short lines (e.g., EDUCATION) treated as headers
    if len(s) <= 40 and s.isupper() and any(ch.isalpha() for ch in s):
        return True
    return False


def normalize_header(line: str) -> str:
    """Map a header line to a canonical section key where possible."""
    s = (line or "").strip(" :\t").lower()
    for canon, variants in SECTION_ALIASES.items():
        for v in variants:
            if s == v or s.startswith(v):
                return canon
    return s


def split_into_lines(text: str) -> List[str]:
    return [ln.rstrip() for ln in (text or "").splitlines()]


def coalesce_bullets(lines: List[str], max_len: int = 400) -> List[str]:
    """
    Collect bullet-ish or short lines as items; ignore obvious headers.
    """
    out: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or is_section_header(s):
            continue
        if BULLET_RE.match(s) or ";" in s:
            parts = [p.strip(" •*-–\t") for p in re.split(r"[;•]", s) if p.strip()]
            for p in parts:
                if 2 <= len(p) <= max_len:
                    out.append(p)
        else:
            if 2 <= len(s) <= max_len:
                out.append(s)
    return out


def split_sections(text: str) -> Dict[str, List[str]]:
    """
    Very fast, heuristic section splitter:
      - Detect headers
      - Bucket following lines until next header
      - Strip headers out of content
    Returns dict: {canonical_section_key: [lines]}
    """
    lines = split_into_lines(text)
    sections: Dict[str, List[str]] = {}
    current = "body"

    for ln in lines:
        if is_section_header(ln):
            current = normalize_header(ln)
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(ln)

    # Clean each section’s content into bullet-ish entries (without headers)
    for k, content_lines in list(sections.items()):
        sections[k] = coalesce_bullets(content_lines)

    return sections


def extract_job_requirements(job_text: str, max_items: int = 50) -> List[str]:
    """
    Extract JD requirements while skipping section headers like:
      'Minimum Qualifications:' / 'Preferred Qualifications:' / 'Responsibilities:' etc.
    """
    lines = split_into_lines(job_text)
    items: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or is_section_header(s):
            continue
        if BULLET_RE.match(s) or 2 <= len(s) <= 300:
            items.append(s)
        if len(items) >= max_items:
            break
    return items
