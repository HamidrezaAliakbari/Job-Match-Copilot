from __future__ import annotations
from typing import Dict, List, Tuple

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
# Common institution/provider cues
INSTITUTION_CUES = [
    "university", "univ.", "college", "institute", "school of", "medical center",
    "vanderbilt", "minnesota", "stanford", "harvard", "mit", "oxford", "citi program"
]


def _is_course_like(text: str) -> bool:
    if not isinstance(text, str):
        return False
    low = text.lower()
    if any(t in low for t in COURSE_HINT_TERMS):
        return True
    # pattern: "<Title> – <Institution>"
    if "–" in text or "-" in text:
        # dash-separated and has an institution cue
        if any(cue in low for cue in INSTITUTION_CUES):
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
    # also check for clinical duty phrases
    return any(t in low for t in CLINICAL_TASK_TERMS)


def _evidence_section(snip: str, resume: Dict) -> str:
    """Map an evidence snippet back to a section, with course/cert overrides."""
    if not isinstance(snip, str):
        return "summary"

    # If it smells like a course/cert, route to courses/education even if it's in experience
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
    return "experience"  # default


def _suggest_for_partial(req: str, evidence: List[str], section_hint: str, ignore_before: bool = False) -> Dict:
    """Suggestion for partially met requirements, section-aware."""
    before = "" if ignore_before else (evidence[0] if evidence else "")

    if section_hint in ("courses", "education"):
        return {
            "target_requirement": req,
            "section": section_hint,
            "change_type": "course_alignment",
            "before": before,
            "after": "Keep titles concise; include provider and completion year if useful. No fabricated metrics.",
            "rationale": "Courses/certifications reflect learning, not outcomes.",
        }

    if section_hint == "skills":
        return {
            "target_requirement": req,
            "section": "skills",
            "change_type": "skill_alignment",
            "before": before,
            "after": "Add or surface the exact tool/term (only if true). Consider grouping skills by theme.",
            "rationale": "Explicit naming improves matching without fabricating experience.",
        }

    # experience/projects → measurable bullet
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
    elif section_hint == "skills":
        after = "Add the specific skill/tool ONLY if you actually used it; otherwise plan a micro-project to earn it."
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
        "rationale": "Align terminology without fabrication; choose the right section for the claim.",
    }


def generate_counterfactuals_by_section(evals: List[Dict], resume: Dict, job: Dict) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
    """
    Return (sectioned_suggestions, flat_list).
    - Course/cert lines never get 'add a metric'.
    - If a duty-like requirement has course evidence, we ignore that course as 'before' and route to Experience.
    """
    sectioned: Dict[str, List[Dict]] = {k: [] for k in SECTION_NAMES}
    flat: List[Dict] = []

    for e in evals:
        req = e.get("requirement", "")
        status = e.get("status", "Missing")
        ev = e.get("evidence", []) or []

        # Decide section: strongest evidence → that section; if none, guess
        if ev:
            first_ev = ev[0]
            ev_section = _evidence_section(first_ev, resume)
        else:
            first_ev = ""
            ev_section = _guess_target_section(req)

        # If requirement is duty-like but evidence is course/cert, route to experience and ignore 'before'
        ignore_before = False
        if _is_verb_led_requirement(req) and ev:
            if _is_course_like(first_ev) or _is_cert_like(first_ev):
                ev_section = "experience"
                ignore_before = True  # don't show the course as the "Before" snippet

        # Build suggestion
        if status == "Partial":
            sug = _suggest_for_partial(req, ev, ev_section, ignore_before=ignore_before)
        elif status == "Missing":
            sug = _suggest_for_missing(req, ev_section)
        else:
            continue

        sectioned.setdefault(sug["section"], []).append(sug)
        flat.append(sug)

    # Optional: add a summary nudge only if we truly have a summary and none queued there
    if (resume.get("summary") or "") and not sectioned["summary"]:
        sectioned["summary"].append({
            "section": "summary",
            "change_type": "tighten_summary",
            "after": "Condense to 1–2 lines with your primary domain/stack and one result tied to the JD.",
            "rationale": "Sharpen positioning; reviewers read this first.",
        })

    return sectioned, flat
