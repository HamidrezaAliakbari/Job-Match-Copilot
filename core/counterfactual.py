from __future__ import annotations
from typing import Dict, List, Tuple

SECTION_NAMES = ["summary", "skills", "experience", "projects", "education"]

def _evidence_section(snip: str, resume: Dict) -> str:
    if not isinstance(snip, str):
        return "summary"
    if snip in (resume.get("experience_bullets") or []):
        return "experience"
    if snip in (resume.get("projects") or []):
        return "projects"
    if snip in (resume.get("education") or []):
        return "education"
    # if a skill token is exactly present
    if any(snip.strip().lower() == s.lower() for s in (resume.get("skills") or [])):
        return "skills"
    return "summary"

def _suggest_for_partial(req: str, evidence: List[str], section_hint: str) -> Dict:
    before = evidence[0] if evidence else ""
    return {
        "target_requirement": req,
        "section": section_hint,
        "change_type": "surface_metric",
        "before": before,
        "after": (before.split(".")[0] + " — add a quantified outcome (%, ms, $, users).").strip() if before else "Add a concise, quantified bullet showing measurable impact.",
        "rationale": "Quantify impact to convert Partial → Met.",
    }

def _suggest_for_missing(req: str, section_hint: str) -> Dict:
    # If missing, propose a section-appropriate update
    if section_hint == "skills":
        after = "Add the specific tool/skill **only if you actually used it**; otherwise plan a micro-project to earn it."
    elif section_hint in ("experience", "projects"):
        after = "Add or adjust one bullet aligning with the JD phrasing; link a public artifact if applicable."
    elif section_hint == "education":
        after = "Add relevant coursework/certifications (e.g., IRB, GCP, HIPAA, or course names) if applicable."
    else:  # summary
        after = "Add a one-liner aligning your focus to the JD (keywords + outcome)."
    return {
        "target_requirement": req,
        "section": section_hint,
        "change_type": "phrasing_or_project",
        "after": after,
        "rationale": "Align terminology or provide verifiable artifact (no fabrication).",
    }

def generate_counterfactuals_by_section(evals: List[Dict], resume: Dict, job: Dict) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
    """Return (sectioned_suggestions, flat_list)."""
    sectioned: Dict[str, List[Dict]] = {k: [] for k in SECTION_NAMES}
    flat: List[Dict] = []

    # Heuristic: infer target section from strongest evidence, else default:
    # for Missing reqs with no evidence, route to 'summary' first; if it's a tool/skill term, route to 'skills'.
    for e in evals:
        req = e["requirement"]
        status = e["status"]
        ev = e.get("evidence", []) or []
        sec_hint = _evidence_section(ev[0], resume) if ev else (
            "skills" if any(w in req.lower() for w in ["python","pytorch","aws","docker","faiss","qdrant","sql","tms","irb","gcp"]) else "summary"
        )
        if status == "Partial":
            sug = _suggest_for_partial(req, ev, sec_hint)
        elif status == "Missing":
            sug = _suggest_for_missing(req, sec_hint)
        else:
            # No suggestion for 'Met'
            continue

        sectioned.setdefault(sug["section"], []).append(sug)
        flat.append(sug)

    # Optional: section-level “meta” prompts to guide rewrites
    if resume.get("summary", "") and not sectioned["summary"]:
        sectioned["summary"].append({
            "section": "summary",
            "change_type": "tighten_summary",
            "after": "Condense to 1–2 lines highlighting your primary stack and 1 quantified win aligned to the JD.",
            "rationale": "Sharpen positioning to match JD keywords and impact.",
        })

    return sectioned, flat
