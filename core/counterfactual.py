from __future__ import annotations
from typing import Dict, List, Optional
import re

# Reuse evaluation & parsing
from core.reason_llm import evaluate_requirements
from core.parse_job import parse_job
from core.parse_resume import parse_resume

# ---------------------------
# Heuristics
# ---------------------------
_SOFT_SKILL_PAT = re.compile(
    r"\b(communication|collaborat(ion|e)|team(work|ing)|lead(ing|ership)|"
    r"stakeholder|interpersonal|problem[-\s]?solv(ing|er)|"
    r"adapt(ab(le|ility))|empathy|time management)\b",
    re.I,
)

def _is_soft_skill(text: str) -> bool:
    return bool(_SOFT_SKILL_PAT.search(text or ""))

def _is_course_line(text: str) -> bool:
    # Simple tell: looks like a course/certificate/title, no verbs, contains 'course' or capitalized sequence
    t = (text or "").strip()
    if not t:
        return False
    if "course" in t.lower() or "cert" in t.lower():
        return True
    # many course-like titles are short and Title-Cased
    words = t.split()
    caps = sum(1 for w in words if w[:1].isupper())
    return len(words) <= 10 and caps >= max(3, len(words) // 2)

def _make_before_after(req: str) -> Dict[str, str]:
    # generic before/after template
    return {
        "before": req,
        "after": f"{req} — add concise proof or context (tool, scope, or outcome) if true.",
    }

def _suggest_for_requirement(req: str, status: str, section: str) -> Dict:
    rule = "summary_alignment" if section == "summary" else "phrasing_or_project"

    # Soft skills → do NOT ask for numbers
    if _is_soft_skill(req):
        return {
            "rule": rule,
            "before": req,
            "after": f"{req} — add a one-liner with situation + your role + outcome (no metrics needed).",
            "why": "Soft skills shouldn’t be forced into %/time/$; keep it truthful and contextual.",
            "section": section,
        }

    # Courses → never ask for metrics
    if section == "courses" or _is_course_line(req):
        return {
            "rule": "course_alignment",
            "before": req,
            "after": f"{req} — add brief relevance (topic, toolstack) or leave as is; no metrics for courses.",
            "why": "Courses certify exposure; metrics aren’t appropriate.",
            "section": "courses",
        }

    # Default technical phrasing
    sug = _make_before_after(req)
    sug.update({
        "rule": rule,
        "why": "Align to JD phrasing and provide verifiable proof without fabrication.",
        "section": section,
    })
    return sug

# ---------------------------
# Public API
# ---------------------------
def generate_counterfactuals(
    resume: Dict,
    job: Dict,
) -> Dict[str, List[Dict]]:
    """
    Returns suggestions grouped by *resume sections*:
      { "Summary": [...], "Skills": [...], "Experience": [...], "Projects": [...], "Education": [...], "Courses": [...] }
    We map each missing/partial requirement to the most suitable resume section.
    """
    # Evaluate once
    evals = evaluate_requirements(
        job.get("requirements") or [],
        resume,
        preferred=job.get("preferred") or [],
    )

    # Decide the best target section for a requirement
    def pick_section(req: str) -> str:
        r = (req or "").lower()
        if any(k in r for k in ["degree", "bachelor", "master", "phd", "university"]):
            return "education"
        if any(k in r for k in ["course", "certificate", "certification"]):
            return "courses"
        if any(k in r for k in ["python", "aws", "fastapi", "pytorch", "docker", "sql", "sklearn", "tensorflow"]):
            # technical hard skills → experience/projects/skills
            # prefer Experience if we already have bullets there
            if resume.get("experience_bullets"):
                return "experience"
            if resume.get("projects"):
                return "projects"
            return "skills"
        if _is_soft_skill(req):
            return "summary"
        # otherwise put into Experience by default
        return "experience"

    buckets: Dict[str, List[Dict]] = {
        "summary": [], "skills": [], "experience": [],
        "projects": [], "education": [], "courses": []
    }

    for ev in evals:
        status = (ev.get("status") or "").lower()
        if status not in ("missing", "partial", "partially met"):
            continue  # only suggest for gaps
        req = ev.get("requirement", "")
        sec = pick_section(req)
        buckets[sec].append(_suggest_for_requirement(req, status, sec))

    # Ensure deterministic order and title-case keys for UI
    out: Dict[str, List[Dict]] = {}
    order = ["summary", "skills", "experience", "projects", "education", "courses"]
    for k in order:
        title = k.capitalize()
        out[title] = buckets[k]
    return out
