# core/parse_job.py
from __future__ import annotations
import re
from typing import Dict, List, Optional

HEADER_ALIASES = {
    "minimum": [
        r"minimum\s+qualifications?",
        r"basic\s+qualifications?",
        r"must[-\s]*have",
        r"required\s+skills?",
        r"requirements?",
    ],
    "preferred": [
        r"preferred\s+qualifications?",
        r"nice\s*to\s*have",
        r"bonus",
        r"good\s+to\s+have",
    ],
    "responsibilities": [
        r"responsibilit(y|ies)",
        r"what\s+you(\'|’)?ll\s+do",
        r"about\s+the\s+role",
        r"duties",
    ],
    "about": [
        r"about\s+the\s+(job|role|team|company)",
        r"description",
        r"overview",
    ],
}

BULLET_RE = re.compile(r"^\s*(?:[-*•–]|(\d+[\.\)]))\s+")
HEADER_LINE_RE = re.compile(r"^\s*[A-Za-z].{0,80}:?\s*$")

def _read_text(path: Optional[str], text: Optional[str]) -> str:
    if text and text.strip():
        return text.strip()
    if not path:
        return ""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()

def _norm_lines(txt: str) -> List[str]:
    # split and clean; keep shortish lines
    raw = [ln.strip() for ln in txt.splitlines()]
    # coalesce very long wrap lines into bullets if they contain semicolons
    out: List[str] = []
    for ln in raw:
        if not ln:
            continue
        # split packed bullets like "a; b; c"
        if ";" in ln and not BULLET_RE.match(ln):
            parts = [p.strip(" •*-–\t") for p in ln.split(";") if p.strip()]
            out.extend(parts)
        else:
            out.append(ln)
    return out

def _is_header(ln: str) -> bool:
    # explicit bullet lines are not headers
    if BULLET_RE.match(ln):
        return False
    # one-liner with trailing colon or header-y structure
    if HEADER_LINE_RE.match(ln) and (ln.endswith(":") or len(ln.split()) <= 6):
        return True
    # match alias lists
    low = ln.lower().rstrip(":").strip()
    for _, pats in HEADER_ALIASES.items():
        for p in pats:
            if re.fullmatch(p, low):
                return True
    return False

def _which_bucket(header_text: str) -> str:
    low = header_text.lower().rstrip(":").strip()
    for bucket, pats in HEADER_ALIASES.items():
        for p in pats:
            if re.search(p, low):
                return bucket
    # fallbacks
    if "responsib" in low or "you’ll do" in low or "youll do" in low:
        return "responsibilities"
    return "about"

def _collect_items(lines: List[str]) -> Dict[str, List[str]]:
    buckets = {
        "minimum_qualifications": [],
        "preferred_qualifications": [],
        "responsibilities": [],
        "about": [],
        "other": [],
    }
    current = "other"
    for ln in lines:
        if not ln:
            continue
        if _is_header(ln):
            b = _which_bucket(ln)
            if b == "minimum":
                current = "minimum_qualifications"
            elif b == "preferred":
                current = "preferred_qualifications"
            elif b == "responsibilities":
                current = "responsibilities"
            elif b == "about":
                current = "about"
            else:
                current = "other"
            continue

        # treat bullets and short lines as items; drop obvious headers
        text = BULLET_RE.sub("", ln).strip()
        if _is_header(text):
            continue
        if 2 <= len(text) <= 400:
            buckets[current].append(text)

    # de-duplicate while preserving order
    for k, arr in buckets.items():
        seen = set()
        uniq: List[str] = []
        for a in arr:
            key = a.lower()
            if key not in seen:
                seen.add(key)
                uniq.append(a)
        buckets[k] = uniq
    return buckets

def parse_job(
    path: Optional[str] = None,
    *,
    text: Optional[str] = None,
    requirements: Optional[List[str]] = None,
    preferred: Optional[List[str]] = None,
) -> Dict:
    """
    Build a normalized job object:
    {
      title: str,
      requirements: [...],          # from Minimum
      preferred: [...],             # from Preferred
      sections: {
        minimum_qualifications: [...],
        preferred_qualifications: [...],
        responsibilities: [...],
        about: [...],
        other: [...]
      }
    }
    """
    raw = _read_text(path, text)
    lines = _norm_lines(raw)
    sections = _collect_items(lines)

    # external overrides
    if requirements:
        sections["minimum_qualifications"] = requirements + sections["minimum_qualifications"]
    if preferred:
        sections["preferred_qualifications"] = preferred + sections["preferred_qualifications"]

    # title heuristic
    title = "Job"
    if lines:
        first = lines[0]
        if len(first) <= 120 and not _is_header(first):
            title = first

    job = {
        "title": title,
        "requirements": sections["minimum_qualifications"],
        "preferred": sections["preferred_qualifications"],
        "sections": sections,
    }
    return job
