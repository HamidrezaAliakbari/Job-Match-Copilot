# core/sectionizer.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

try:
    from joblib import load as joblib_load  # type: ignore
except Exception:
    joblib_load = None  # type: ignore

CANON = {
    "SUMMARY": ["summary", "professional summary", "profile", "about me", "objective"],
    "SKILLS": ["skills", "technical skills", "core skills", "tooling", "technologies"],
    "EXPERIENCE": [
        "experience", "professional experience", "work experience", "employment",
        "work history", "relevant experience", "industry experience"
    ],
    "PROJECTS": ["projects", "selected projects", "academic projects", "personal projects"],
    "EDUCATION": [
        "education", "academic background", "academics", "education & training",
        "education and training"
    ],
    "COURSES": ["courses", "relevant coursework", "coursework"],
    "CERTIFICATIONS": ["certifications", "certs", "licenses", "certification"],
    "PUBLICATIONS": ["publications", "papers", "articles"],
    "HONORS": ["honors", "awards", "honors & awards", "awards & honors"],
    "VOLUNTEER": ["volunteer", "volunteering", "community service"],
    "AFFILIATIONS": ["affiliations", "memberships", "professional memberships"],
    "CONTACT": ["contact", "contact information", "personal details"],
    "MISC": ["misc", "additional", "other", "additional information"],
}

HEADER_MAP: Dict[str, str] = {}
for canon, aliases in CANON.items():
    for a in aliases:
        HEADER_MAP[a.lower()] = canon

BULLET = re.compile(r"^\s*([\-*•–]|(\d+[\.\)]))\s+")
HEADER_LINE = re.compile(r"^\s*([A-Z][A-Za-z0-9 &/+\-]|[A-Z]{3,})(?:\s*[:：])?\s*$")
POSSIBLE_HEADER_KEYWORDS = re.compile(r"(education|experience|skills|summary|projects?|course|certification|publication|honors?|awards?|volunteer|affiliations?)", re.I)
YEAR = r"(19|20)\d{2}"
DATE_RANGE = re.compile(fr"({YEAR})(\s*[–\-–]\s*| to )({YEAR}|present|current)", re.I)
DEGREE = re.compile(r"(B\.?S\.?|M\.?S\.?|BSc|MSc|Ph\.?D\.?|MBA|MD|DDS|DO|BA|MA|MEng|BEng|MPhil|DPhil|MS|BS)", re.I)
UNIVERSITY = re.compile(r"(university|institute|college|polytechnic|school of|faculty of)", re.I)
GPA = re.compile(r"\bGPA[:\s]*(\d\.\d{1,2})", re.I)
LOOKS_COURSE = re.compile(r"(?i)\b(course|coursework|module|class|laboratory|lab|seminar)\b")
HARD_SKILL_HINT = re.compile(r"(?i)\b(python|pytorch|tensorflow|fastapi|docker|aws|qdrant|mlflow|nlp|sql|excel|sas|matlab|r\b|java|c\+\+|javascript|tableau|powerbi|git|kubernetes|linux)\b")

@dataclass
class Line:
    text: str
    idx: int
    is_bullet: bool
    looks_header: bool

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def _header_to_canon(header_text: str) -> Optional[str]:
    key = _norm(header_text).strip(":：").lower()
    key = re.sub(r"[^a-z0-9 &/+\-]", "", key)
    if key in HEADER_MAP:
        return HEADER_MAP[key]
    m = POSSIBLE_HEADER_KEYWORDS.search(header_text)
    if not m:
        return None
    kw = m.group(1).lower()
    for canon, aliases in CANON.items():
        if any(kw in a for a in aliases):
            return canon
    return None

def _split_lines(text: str) -> List[Line]:
    raw = text.splitlines()
    out: List[Line] = []
    for i, ln in enumerate(raw):
        if not ln.strip():
            continue
        out.append(
            Line(
                text=_norm(ln),
                idx=i,
                is_bullet=bool(BULLET.match(ln)),
                looks_header=bool(HEADER_LINE.match(ln) or POSSIBLE_HEADER_KEYWORDS.search(ln)),
            )
        )
    return out

def _basic_rules_assign(lines: List[Line]) -> List[Tuple[int, str]]:
    assigned: List[Tuple[int, str]] = []
    current: str = "SUMMARY"
    seen_any_header = False

    for ln in lines:
        canon = None
        if ln.looks_header:
            if len(ln.text) <= 64:
                canon = _header_to_canon(ln.text)
        if canon:
            current = canon
            seen_any_header = True
            continue

        if not seen_any_header and ln.idx <= 8 and not ln.is_bullet:
            assigned.append((ln.idx, "SUMMARY"))
            continue
        if DEGREE.search(ln.text) or UNIVERSITY.search(ln.text) or GPA.search(ln.text):
            assigned.append((ln.idx, "EDUCATION"))
            continue
        if DATE_RANGE.search(ln.text) or re.search(r"(?i)\b(intern|engineer|analyst|manager|research|coordinator)\b", ln.text):
            assigned.append((ln.idx, "EXPERIENCE"))
            continue
        if LOOKS_COURSE.search(ln.text):
            assigned.append((ln.idx, "COURSES"))
            continue
        if HARD_SKILL_HINT.search(ln.text) and ("," in ln.text or ln.is_bullet or len(ln.text) <= 80):
            assigned.append((ln.idx, "SKILLS"))
            continue
        if re.search(r"(?i)\bproject(s)?\b", ln.text):
            assigned.append((ln.idx, "PROJECTS"))
            continue
        assigned.append((ln.idx, current))
    return assigned

def _optional_ml_assign(lines: List[Line], rules_labels: List[str], model_path: str) -> Optional[List[str]]:
    if joblib_load is None:
        return None
    try:
        model = joblib_load(model_path)
    except Exception:
        return None
    X = [f"[RULE={r}] {ln.text}" for ln, r in zip(lines, rules_labels)]
    try:
        preds = model.predict(X)
        preds = [p if p in CANON else rl for p, rl in zip(preds, rules_labels)]
        return preds
    except Exception:
        return None

def _segment_from_labels(lines: List[Line], labels: List[str]) -> Dict[str, Dict[str, any]]:
    buckets: Dict[str, List[Line]] = defaultdict(list)
    for ln, lab in zip(lines, labels):
        buckets[lab].append(ln)

    sections: Dict[str, Dict[str, any]] = {}
    for lab, grp in buckets.items():
        confidence = 0.4 + min(0.6, 0.02 * len(grp))
        if lab == "EDUCATION" and any(DEGREE.search(ln.text) or UNIVERSITY.search(ln.text) for ln in grp):
            confidence = max(confidence, 0.75)
        if lab == "SKILLS" and any("," in ln.text or HARD_SKILL_HINT.search(ln.text) for ln in grp):
            confidence = max(confidence, 0.7)
        if lab == "EXPERIENCE" and any(DATE_RANGE.search(ln.text) for ln in grp):
            confidence = max(confidence, 0.7)
        text = "\n".join(ln.text for ln in grp)
        sections[lab] = {
            "lines": [ln.idx for ln in grp],
            "text": text,
            "confidence": round(float(confidence), 2),
        }
    return sections

def sectionize_text(text: str, model_path: str = "models/sectionizer.joblib") -> Dict[str, Dict[str, any]]:
    text = text.replace("\r\n", "\n")
    lines = _split_lines(text)
    if not lines:
        return {}
    rules_assign_pairs = _basic_rules_assign(lines)
    rules_labels = [lab for _, lab in sorted(rules_assign_pairs, key=lambda x: x[0])]
    ml_labels = _optional_ml_assign(lines, rules_labels, model_path)
    labels = ml_labels if ml_labels else rules_labels
    sections = _segment_from_labels(lines, labels)

    if "SUMMARY" in sections:
        topmost_line = min(sections["SUMMARY"]["lines"]) if sections["SUMMARY"]["lines"] else 0
        if topmost_line > 15 and sections["SUMMARY"]["confidence"] < 0.6:
            misc = sections.get("MISC", {"lines": [], "text": "", "confidence": 0.5})
            misc["lines"] += sections["SUMMARY"]["lines"]
            misc["text"] = (misc["text"] + "\n" + sections["SUMMARY"]["text"]).strip()
            sections["MISC"] = misc
            del sections["SUMMARY"]

    if "EXPERIENCE" in sections:
        exp_text = sections["EXPERIENCE"]["text"]
        lines_exp = [ln for ln in exp_text.splitlines() if not LOOKS_COURSE.search(ln)]
        course_lines = [ln for ln in exp_text.splitlines() if LOOKS_COURSE.search(ln)]
        if course_lines:
            sections["EXPERIENCE"]["text"] = "\n".join(lines_exp).strip()
            c = sections.get("COURSES", {"lines": [], "text": "", "confidence": 0.7})
            c["text"] = (c["text"] + "\n" + "\n".join(course_lines)).strip()
            sections["COURSES"] = c

    for k in list(sections.keys()):
        sections[k]["text"] = sections[k]["text"].strip()
    return sections
