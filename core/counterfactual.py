from __future__ import annotations
from typing import Dict, List, Tuple

# Added "courses" so UI and logic can group suggestions there:
SECTION_NAMES = ["summary", "skills", "experience", "projects", "education", "courses"]

COURSE_HINT_TERMS = [
    "course", "coursera", "edx", "udacity", "udemy", "bootcamp", "nanodegree",
    "relevant coursework", "certificate", "certification", "workshop", "seminar"
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
    # heuristic: text smells like a course
    low = snip.lower().strip()
    if any(t in low for t in COURSE_HINT_TERMS):
        return "courses"
    return "summary"

def _suggest_for_partial(req: str, evidence: List[str], section_hint: str) -> Dict:
    """Generate a suggestion for partially met requirements, respecting section semantics."""
    before = evidence[0] if evidence else ""
    if section_hint == "courses":
        # Courses are not experience bullets; do NOT suggest metrics
        return {
            "target_requirement": req,
            "section": "courses",
            "change_type": "course_alignment",
            "before": before,
            "after": "Keep course titles concise. Optionally add provider and completion year; do not add fabricated metrics.",
            "rationale": "Courses represent learning, not outcomes; align naming/provider instead of metrics.",
        }
    # Default path: suggest quantification for experience/projects
    return {
        "target_requirement": req,
        "section": section_hint,
        "change_type": "surface_metric",
        "before": before,
        "after": (before.split(".")[0] + " — add a quantified outcome (%, ms, $, users).").strip() if before else "Add a concise, quantified bullet showing measurable impact.",
        "rationale": "Quantify impact to convert Partial → Met.",
    }

def _suggest_for_missing(req: str, section_hint: str) -> Dict:
    """Generate a suggestion for missing requirements, section-aware."""
    if section_hint == "courses":
        after = "List a directly relevant course/cert (provider + year) if truly completed; otherwise plan a short micro-course."
    elif section_hint == "skills":
        after = "Add the specific tool/skill ONLY if you actually used it; otherwise plan a micro-project to earn it."
    elif section_hint in ("experience", "projects"):
        after = "Add or adjust one bullet aligning with the JD phrasing; link a public artifact if applicable."
    elif section_hint == "education":
        after = "Add relevant coursework/certifications (e.g., IRB, GCP, HIPAA) if applicable."
    else:  # summary
        after = "Add a one-liner aligning your focus to the JD (keywords + outcome)."
    return {
        "target_requirement": req,
        "section": section_hint,
        "change_type": "phrasing_or_project" if section_hint != "courses" else "course_alignment",
        "after": after,
        "rationale": "Align terminology to the JD while avoiding fabrication.",
    }

def generate_counterfactuals_by_section(evals: List[Dict], resume: Dict, job: Dict) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
    """Return (sectioned_suggestions, flat_list). Course entries never get 'add a metric' prompts."""
    sectioned: Dict[str, List[Dict]] = {k: [] for k in SECTION_NAMES}
    flat: List[Dict] = []

    for e in evals:
        req = e["requirement"]
        status = e["status"]
        ev = e.get("evidence", []) or []

        # Decide section: strongest evidence -> section; if none, route skills or summary heuristically
        if ev:
            sec_hint = _evidence_section(ev[0], resume)
        else:
            low = req.lower()
            if any(term in low for term in ["python", "pytorch", "aws", "docker", "faiss", "qdrant", "sql", "tms", "irb", "gcp", "hipaa"]):
                sec_hint = "skills"
            elif any(term in low for term in ["course", "certificate", "workshop", "seminar"]):
                sec_hint = "courses"
            else:
                sec_hint = "summary"

        if status == "Partial":
            sug = _suggest_for_partial(req, ev, sec_hint)
        elif status == "Missing":
            sug = _suggest_for_missing(req, sec_hint)
        else:
            continue

        sectioned.setdefault(sug["section"], []).append(sug)
        flat.append(sug)

    # Optional: add a gentle summary tightening if none were added
    if (resume.get("summary") or "") and not sectioned["summary"]:
        sectioned["summary"].append({
            "section": "summary",
            "change_type": "tighten_summary",
            "after": "Condense to 1–2 lines with your primary stack and one quantified win tied to the JD.",
            "rationale": "Sharpen positioning; this is the first thing reviewers read.",
        })

    return sectioned, flat
