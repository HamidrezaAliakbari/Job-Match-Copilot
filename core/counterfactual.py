from __future__ import annotations
from typing import Dict, List, Tuple

# We now include courses explicitly
SECTION_NAMES = ["summary", "skills", "experience", "projects", "education", "courses"]

# Heuristic term banks
COURSE_HINT_TERMS = [
    "course", "coursework", "relevant coursework", "certificate", "certification",
    "coursera", "edx", "udacity", "udemy", "bootcamp", "nanodegree", "workshop", "seminar"
]
CERT_HINT_TERMS = ["irb", "gcp", "hipaa", "citi"]  # usually belong under Education
SKILL_HINT_TERMS = [
    "python","pytorch","tensorflow","fastapi","docker","aws","faiss","qdrant","sql",
    "tms","tes","redis","spark","pandas","mlflow","spacy","presidio"
]
VERB_HEADS = [
    "conduct", "conducts", "verify", "verifies", "manage", "manages", "maintain", "maintains",
    "collect", "collects", "organize", "organizes", "document", "documents",
    "assist", "assists", "administer", "administers", "perform", "performs",
    "recruit", "recruits", "screen", "screens", "enroll", "enrolls",
    "obtain", "obtains", "update", "updates", "write", "writes",
    "monitor", "monitors", "evaluate", "evaluates", "develop", "develops",
    "prepare", "prepares"
]

CLINICAL_TASK_TERMS = [
    "informed consent", "inclusion/exclusion", "irb", "regulatory", "qa/qc",
    "recruitment", "screening", "enrollment", "psychiatric assessments",
    "questionnaires", "library searches", "tms", "tes", "phlebotomy", "binder"
]


def _evidence_section(snip: str, resume: Dict) -> str:
    """Map an evidence snippet back to a resume section."""
    if not isinstance(snip, str):
        return "summary"
    if snip in (resume.get("experience_bullets") or []):
        return "experience"
    if snip in (resume.get("projects") or []):
        return "projects"
    if snip in (resume.get("education") or []):
        return "education"
    if snip in (resume.get("courses") or []):
        return "courses"
    # exact skill match
    if any(snip.strip().lower() == s.lower() for s in (resume.get("skills") or [])):
        return "skills"
    # heuristic: smells like a course
    low = snip.lower().strip()
    if any(t in low for t in COURSE_HINT_TERMS):
        return "courses"
    return "summary"


def _guess_target_section(req: str) -> str:
    """Decide section for requirements with NO evidence."""
    low = req.lower().strip()

    # Courses/certs first
    if any(t in low for t in CERT_HINT_TERMS):
        return "education"  # IRB/GCP/HIPAA/CITI are formal certifications
    if any(t in low for t in COURSE_HINT_TERMS):
        return "courses"

    # Skill/tool terms
    if any(t in low for t in SKILL_HINT_TERMS):
        return "skills"

    # Clinical operational tasks → experience
    if any(t in low for t in CLINICAL_TASK_TERMS):
        return "experience"

    # Verb-led responsibilities → experience
    first_word = low.split(" ", 1)[0] if low else ""
    if first_word in VERB_HEADS:
        return "experience"

    # Default to experience rather than summary
    return "experience"


def _suggest_for_partial(req: str, evidence: List[str], section_hint: str) -> Dict:
    """Suggestion for partially met requirements, respecting section semantics."""
    before = evidence[0] if evidence else ""

    if section_hint == "courses" or section_hint == "education":
        # Do NOT ask for metrics here
        return {
            "target_requirement": req,
            "section": section_hint,
            "change_type": "course_alignment",
            "before": before,
            "after": "Keep titles concise; include provider and completion year if useful. No fabricated metrics.",
            "rationale": "Courses/certifications reflect learning, not outcomes.",
        }

    if section_hint == "skills":
        # Suggest adding/ordering skills, not metrics
        return {
            "target_requirement": req,
            "section": "skills",
            "change_type": "skill_alignment",
            "before": before,
            "after": "Add or surface the exact tool/term (only if true). Consider grouping skills by theme.",
            "rationale": "Explicit naming improves matching without fabricating experience.",
        }

    # Experience/projects → encourage measurable bullet
    return {
        "target_requirement": req,
        "section": section_hint,
        "change_type": "surface_metric",
        "before": before,
        "after": (before.split(".")[0] + " — add a quantified outcome (%, time, $, users, sample size).").strip()
                 if before else f"Add one bullet aligned to: '{req}' (tools, scale, frequency, stakeholders, impact).",
        "rationale": "Measurable bullets convert Partial → Met.",
    }


def _suggest_for_missing(req: str, section_hint: str) -> Dict:
    """Suggestion for missing requirements, section-aware."""
    if section_hint in ("courses", "education"):
        after = "List a directly relevant course/cert (provider + year) if completed; otherwise plan a short course."
        change_type = "course_alignment"
    elif section_hint == "skills":
        after = "Add the specific skill/tool ONLY if you actually used it; otherwise plan a micro-project to earn it."
        change_type = "skill_alignment"
    elif section_hint in ("experience", "projects"):
        after = f"Add one bullet aligned to: '{req}' (tools used, volume/sample size, cadence, stakeholders, outcome)."
        change_type = "phrasing_or_project"
    else:  # summary (rare now)
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
    """Return (sectioned_suggestions, flat_list). Courses/certs never get 'add a metric' prompts."""
    sectioned: Dict[str, List[Dict]] = {k: [] for k in SECTION_NAMES}
    flat: List[Dict] = []

    for e in evals:
        req = e["requirement"]
        status = e["status"]
        ev = e.get("evidence", []) or []

        # Decide section: strongest evidence → that section; if none, use smarter guesser
        if ev:
            sec_hint = _evidence_section(ev[0], resume)
        else:
            sec_hint = _guess_target_section(req)

        if status == "Partial":
            sug = _suggest_for_partial(req, ev, sec_hint)
        elif status == "Missing":
            sug = _suggest_for_missing(req, sec_hint)
        else:
            continue

        sectioned.setdefault(sug["section"], []).append(sug)
        flat.append(sug)

    # Optional: only add a summary nudge if we truly have a summary and nothing else queued there
    if (resume.get("summary") or "") and not sectioned["summary"]:
        sectioned["summary"].append({
            "section": "summary",
            "change_type": "tighten_summary",
            "after": "Condense to 1–2 lines with your primary domain/stack and one result tied to the JD.",
            "rationale": "Sharpen positioning; reviewers read this first.",
        })

    return sectioned, flat
