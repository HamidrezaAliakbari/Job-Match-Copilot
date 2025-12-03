# core/sectionizer.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import re

# ---------- shared helpers ----------
_WS = re.compile(r"\s+")
_BULLET = re.compile(r"^\s*(?:[-*•–]|(\d{1,3}[.)]))\s+")
_HEADER_TRAIL = re.compile(r"[:：\-\s]*$")

def norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip())

def is_header(line: str) -> bool:
    l = (line or "").strip()
    if not l:
        return False
    # obvious headers (case-insensitive, strip punctuation)
    candidates = [
        "professional summary", "summary", "objective",
        "experience", "work experience", "employment",
        "projects", "selected projects",
        "education", "academics",
        "skills", "technical skills",
        "courses", "coursework", "certifications", "certificates",
        "publications", "research",
        "activities", "awards",
    ]
    h = _HEADER_TRAIL.sub("", l).lower()
    return h in candidates

def clean_header(line: str) -> str:
    return _HEADER_TRAIL.sub("", (line or "").strip())

def take_bullets(lines: List[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        if _BULLET.match(ln):
            out.append(_BULLET.sub("", ln).strip())
        else:
            out.append(ln.strip())
    return out

def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        k = it.lower()
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out

# ---------- resume sectionizer ----------
RESUME_SECTION_KEYS = {
    "summary": {"professional summary", "summary", "objective"},
    "experience": {"experience", "work experience", "employment"},
    "projects": {"projects", "selected projects"},
    "education": {"education", "academics"},
    "skills": {"skills", "technical skills"},
    "courses": {"courses", "coursework", "certifications", "certificates"},
}

def sectionize_resume_text(text: str) -> Dict[str, List[str] | str]:
    """
    Parse a raw pasted resume into structured buckets:
      summary(str), skills[List[str]], experience_bullets[List[str]],
      projects[List[str]], education[List[str]], courses[List[str]]
    """
    lines = [norm(l) for l in (text or "").splitlines()]
    # collect sections
    current = "summary"  # default to summary until we hit an explicit header
    buckets: Dict[str, List[str]] = {
        "skills": [],
        "experience_bullets": [],
        "projects": [],
        "education": [],
        "courses": [],
    }
    summary_chunks: List[str] = []

    def map_header(h: str) -> str:
        h = clean_header(h).lower()
        for key, names in RESUME_SECTION_KEYS.items():
            if h in names:
                # map to our internal field names
                if key == "experience":
                    return "experience_bullets"
                return key
        # unknown header → treat as experience
        return "experience_bullets"

    for raw in lines:
        if not raw:
            continue
        if is_header(raw):
            current = map_header(raw)
            continue
        # route line into bucket
        if current == "skills":
            # split by separators
            parts = re.split(r"[,\u2022;|/]+", raw)
            for p in parts:
                t = p.strip()
                if t and len(t) <= 64:
                    buckets["skills"].append(t)
        elif current in buckets:
            buckets[current].append(raw)
        else:
            # default to summary chunks
            summary_chunks.append(raw)

    # post-process
    for k in ("experience_bullets", "projects", "education", "courses"):
        buckets[k] = take_bullets(buckets[k])  # type: ignore[assignment]

    buckets["skills"] = dedupe_keep_order(buckets["skills"])  # type: ignore[assignment]
    summary = " ".join(summary_chunks).strip()

    return {
        "summary": summary,
        "skills": buckets["skills"],
        "experience_bullets": buckets["experience_bullets"],
        "projects": buckets["projects"],
        "education": buckets["education"],
        "courses": buckets["courses"],
    }

# ---------- job sectionizer ----------
JOB_HEADERS = {
    "minimum": {
        "minimum qualifications", "basic qualifications", "requirements",
        "must have", "you have", "what you’ll need"
    },
    "preferred": {
        "preferred qualifications", "nice to have", "bonus", "good to have",
        "strongly preferred"
    },
    "about": {
        "about the role", "about the job", "role", "responsibilities",
        "what you’ll do", "what you will do"
    },
    "title": {"job title", "title", "position"},
}

def is_job_header(line: str) -> Optional[str]:
    l = clean_header(line).lower()
    for bucket, names in JOB_HEADERS.items():
        if l in names:
            return bucket
    return None

def sectionize_job_text(text: str,
                        explicit_requirements: Optional[List[str]] = None,
                        explicit_preferred: Optional[List[str]] = None) -> Dict[str, List[str] | str]:
    """
    From a raw JD, extract:
      title(str), requirements[List[str]], preferred[List[str]]
    Ignore header lines as requirements.
    """
    if explicit_requirements or explicit_preferred:
        return {
            "title": "",
            "requirements": dedupe_keep_order(explicit_requirements or []),
            "preferred": dedupe_keep_order(explicit_preferred or []),
        }

    lines = [norm(l) for l in (text or "").splitlines()]
    bucket = None
    title = ""
    reqs: List[str] = []
    prefs: List[str] = []

    buf: List[str] = []

    def flush_into(target: List[str]):
        if not buf:
            return
        merged = " ".join(buf).strip()
        buf.clear()
        if merged:
            parts = [p.strip() for p in re.split(r"[•;]\s+|\n", merged) if p.strip()]
            if parts:
                target.extend(parts)
            else:
                target.append(merged)

    for raw in lines:
        if not raw:
            continue
        bh = is_job_header(raw)
        if bh:
            # flush previous buffer
            if bucket == "minimum":
                flush_into(reqs)
            elif bucket == "preferred":
                flush_into(prefs)
            bucket = bh
            continue

        if bucket == "title" and not title:
            title = raw
            continue

        if bucket == "minimum":
            if _BULLET.match(raw):
                reqs.append(_BULLET.sub("", raw).strip())
            else:
                buf.append(raw)
            continue

        if bucket == "preferred":
            if _BULLET.match(raw):
                prefs.append(_BULLET.sub("", raw).strip())
            else:
                buf.append(raw)
            continue

        # ignore "about" for requirements

    # flush tail
    if bucket == "minimum":
        flush_into(reqs)
    elif bucket == "preferred":
        flush_into(prefs)

    # remove any residual header-like entries that slipped in
    header_like = {*(h for names in JOB_HEADERS.values() for h in names)}
    reqs = [r for r in reqs if clean_header(r).lower() not in header_like]
    prefs = [r for r in prefs if clean_header(r).lower() not in header_like]

    reqs = dedupe_keep_order(reqs)
    prefs = dedupe_keep_order(prefs)

    return {
        "title": title,
        "requirements": reqs,
        "preferred": prefs,
    }
