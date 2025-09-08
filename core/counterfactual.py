from __future__ import annotations
from typing import Dict, List, Tuple
import re

SECTION_NAMES = ["summary", "skills", "experience", "projects", "education", "courses"]

# Term banks
COURSE_HINT_TERMS = [
    "course", "coursework", "relevant coursework", "certificate", "certification",
    "coursera", "edx", "udacity", "udemy", "bootcamp", "nanodegree", "workshop", "seminar"
]
CERT_HINT_TERMS = ["irb", "gcp", "hipaa", "citi"]  # certifications -> education
SKILL_HINT_TERMS = [
    "python","pytorch","tensorflow","fastapi","docker","aws","faiss","qdrant","sql",
    "tms","tes","redis","spark","pandas","mlflow","spacy","presidio"
]
# Duties typically start with these verbs (for routing when there is NO evidence)
VERB_HEADS = [
    "conduct","conducts","verify","verifies","manage","manages","maintain","maintains",
    "collect","collects","organize","organizes","document","documents","assist","assists",
    "administer","administers","perform","performs","recruit","recruits","screen","screens",
    "enroll","enrolls","obtain","obtains","update","updates","write","writes","monitor","monitors",
    "evaluate","evaluates","develop","develops","prepare","prepares","coordinate","coordinates"
]
CLINICAL_TASK_TERMS = [
    "informed consent", "inclusion/exclusion", "irb", "regulatory", "qa/qc",
    "recruitment", "screening", "enrollment", "psychiatric assessments",
    "questionnaires", "library searches", "tms", "tes", "phlebotomy", "binder"
]
# Soft skills (never ask for metrics)
SOFT_SKILL_TERMS = [
    "communication","communicator","teamwork","collaboration","collaborative","leadership",
    "detail-oriented","motivated","self-starter","problem solving","problem-solving",
    "interpersonal","time management","adaptability","critical thinking","organized",
    "stakeholder management","ownership","work ethic","fast learner"
]

# Institution/provider cues (for course-like lines)
INSTITUTION_CUES = [
    "university", "univ.", "college", "institute", "school of", "medical center",
    "vanderbilt", "minnesota", "stanford", "harvard", "mit", "oxford", "citi program"
]

# -------- detectors --------

_METRIC_REGEXES = [
    re.compile(r"\b\d+(\.\d+)?\s*%\b"),                        # 12.5%
    re.compile(r"\bp\d{2}\b"),                                 # p95, p99
    re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|secs|seconds|minutes|min|hrs|hours|days|weeks|mos?|months|yrs?|years)\b"),
    re.compile(r"\b\d+(\.\d+)?\s*(k|m|b|million|billion|thousand)\b", re.I),  # 10k, 2M, million
    re.compile(r"\b(n\s*=\s*\d+)\b", re.I),                    # n=123
    re.compile(r"\$\s*\d[\d,\.]*"),                            # $10,000
]

def _has_metric_like(text: str) -> bool:
    if not isinstance(text, str):
        return False
    low = text.lower()
    # quick positives
    if "%" in text or "$" in text:
        return True
    for rgx in _METRIC_REGEXES:
        if rgx.search(low):
            return True
    return False

def _is_soft_skill(text: str) -> bool:
    low = (text or "").lower()
    return any(term in low for term in SOFT_SKILL_TERMS)

def _is_course_like(text: str) -> bool:
    if not isinstance(text, str):
        return False
    low = text.lower()
    if any(t in low for t in COURSE_HINT_TERMS):
        return True
    # pattern: "<Title> – <Institution>" or "-" with institution cue
    if ("–" in text or "-" in text) and any(cue in low for cue in INSTITUTION_CUES):
        return True
    return False

def _is_cert_like(text: str) -> bool:
    low = (text or "").lower()
    return any(t in low for t in CERT_HINT_TERMS) or "certif" in low

def _is_verb_led_requirement(req: str) -> bool:
    low = (req or "").lower().strip()
    if not low:
        return False
    first = low.split(" ", 1)[0]
    if first in VERB_HEADS:
        return True
    return any(t in low for t in CLINICAL_TASK_TERMS)

# -------- section mapping --------

def _evidence_section(snip: str, resume: Dict) -> str:
    """Map an evidence snippet back to a section, with course/cert overrides."""
    if not isinstance(snip, str):
        return "summary"

    # Respect course/cert wherever they appear
    if _is_cert_like(snip):
        return "education"
    if _is_course_like(snip):
        return "courses"

    if snip in (resume.get("experience_bullets") or []):
        return "experience"
    if snip in (resume.get("projects") or []):
        return "projects"
    if snip in (resume.get("education") or []):
        return "education"
    if snip in (resume.get("courses") or []):
        return "courses"
    if any(snip.strip().lower() == s.lower() for s in (resume.get("skills") or [])):
        return "skills"
    return "summary"

def _guess_target_section(req: str) -> str:
    """Decide section for requirements with NO evidence."""
    low = (req or "").lower().strip()
    if any(t in low for t in CERT_HINT_TERMS):
        return "education"
    if any(t in low for t in COURSE_HINT_TERMS):
        return "courses"
    if any(t in low for t in SKILL_HINT_TERMS):
        return "skills"
    if any(t in low for t in CLINICAL_TASK_TERMS):
        return "experience"
    first = low.split(" ", 1)[0] if low else ""
    if first in VERB_HEADS:
        return "experience"
    # Prefer experience over summary as default
    return "experience"

# -------- suggestion builders --------

def _suggest_for_partial(req: str, evidence: List[str], section_hint: str, keep_origin: bool = True) -> Dict:
    """
    Build suggestion for partially met reqs.
    Rules:
      - Courses/Education: never metrics.
      - Soft skills: never metrics.
      - If 'before' already has metrics, don't ask for more; tighten phrasing instead.
      - Section stays as 'section_hint' (origin), unless keep_origin is False (we don't use that here).
    """
    before = evidence[0] if evidence else ""
    before_has_metric = _has_metric_like(before)
    req_is_soft = _is_soft_skill(req) or _is_soft_skill(before)

    if section_hint in ("courses", "education"):
        return {
            "target_requirement": req,
            "section": section_hint,
            "change_type": "course_alignment",
            "before": before,
            "after": "Keep titles concise; include provider and completion year if useful. No fabricated metrics.",
            "rationale": "Courses/certifications reflect learning, not outcomes.",
        }

    if section_hint == "skills" or req_is_soft:
        return {
            "target_requirement": req,
            "section": section_hint,
            "change_type": "tighten_phrasing",
            "before": before,
            "after": "Clarify context (tool/domain) or relocate to Summary/Skills; avoid forcing numbers for soft skills.",
            "rationale": "Soft skills and skill lists should not use artificial metrics.",
        }

    if before_has_metric:
        return {
            "target_requirement": req,
            "section": section_hint,
            "change_type": "tighten_phrasing",
            "before": before,
            "after": "Refine for clarity: emphasize scope, stakeholders, or outcome alignment to the JD without adding more numbers.",
            "rationale": "Already quantified; focus on clarity and relevance.",
        }

    # Experience/projects → encourage a measurable bullet (only if not soft and not already quantified)
    return {
        "target_requirement": req,
        "section": section_hint,
        "change_type": "surface_metric",
        "before": before,
        "after": (before.split(".")[0] + " — add a quantified outcome (%, time, $, users, sample size).").strip()
                 if before else f"Add one bullet aligned to: '{req}' (tools, scale, frequency, stakeholders, outcome).",
        "rationale": "Measurable bullets convert Partial → Met.",
    }

def _suggest_for_missing(req: str, section_hint: str) -> Dict:
    if section_hint in ("courses", "education"):
        after = "List a directly relevant course/cert (provider + year) if completed; otherwise plan a short course."
        change_type = "course_alignment"
    elif section_hint == "skills" or _is_soft_skill(req):
        after = "Add the exact tool/term (only if true) or include brief context; avoid inventing metrics."
        change_type = "skill_alignment"
    elif section_hint in ("experience", "projects"):
        after = f"Add one bullet aligned to: '{req}' (tools used, volume/sample size, cadence, stakeholders, outcome)."
        change_type = "phrasing_or_project"
    else:
        after = "Optional: add a one-liner to position your focus to the JD (keywords + outcome)."
        change_type = "summary_alignment"

    return {
        "target_requirement": req,
        "section": section_hint,
        "change_type": change_type,
        "after": after,
        "rationale": "Align terminology without fabrication; keep edits appropriate to the section.",
    }

# -------- main --------

def generate_counterfactuals(evals: List[Dict], resume: Dict, job: Dict) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
    """
    Return (sectioned_suggestions, flat_list).

    Guarantees:
      - If evidence exists, the suggestion's section == evidence's section (origin preserved).
      - Course/cert lines never get 'add a metric'.
      - Soft skills never get metric prompts.
      - If 'before' already has a metric (e.g., '7+ years'), we suggest tightening, not more metrics.
    """
    sectioned: Dict[str, List[Dict]] = {k: [] for k in SECTION_NAMES}
    flat: List[Dict] = []

    for e in evals:
        req = e.get("requirement", "")
        status = e.get("status", "Missing")
        ev = e.get("evidence", []) or []

        # Section origin rule:
        if ev:
            sec_hint = _evidence_section(ev[0], resume)
        else:
            sec_hint = _guess_target_section(req)

        if status == "Partial":
            sug = _suggest_for_partial(req, ev, sec_hint, keep_origin=True)
        elif status == "Missing":
            sug = _suggest_for_missing(req, sec_hint)
        else:
            continue

        sectioned.setdefault(sug["section"], []).append(sug)
        flat.append(sug)

    if (resume.get("summary") or "") and not sectioned["summary"]:
        sectioned["summary"].append({
            "section": "summary",
            "change_type": "tighten_summary",
            "after": "Condense to 1–2 lines with your primary domain/stack and one result tied to the JD.",
            "rationale": "Sharpen positioning; reviewers read this first.",
        })

    return sectioned, flat
