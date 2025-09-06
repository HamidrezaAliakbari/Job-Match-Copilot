from __future__ import annotations
from typing import Dict, List

def generate_counterfactuals(evals: List[Dict], resume: Dict) -> List[Dict]:
    suggestions: List[Dict] = []
    for e in [x for x in evals if x["status"] == "Partial"][:2]:
        before = e["evidence"][0] if e["evidence"] else ""
        suggestions.append({
            "target_requirement": e["requirement"],
            "change_type": "surface_metric",
            "before": before,
            "after": (before.split(".")[0] + " — add a quantified outcome").strip(),
            "rationale": "Quantify impact to convert Partial → Met."
        })
    for e in [x for x in evals if x["status"] == "Missing"][:3]:
        suggestions.append({
            "target_requirement": e["requirement"],
            "change_type": "phrasing_or_project",
            "after": "Add a bullet aligned to the JD phrasing if true, OR link a small repo/notebook.",
            "rationale": "Align terminology or provide verifiable artifact (no fabrication)."
        })
    return suggestions
