from __future__ import annotations
from typing import Dict, List
from core.score import compute_match_score

def decide_action(evaluations: List[Dict]) -> Dict:
    """
    Simple, transparent rule set:
      - score >= 0.75 → "interview"
      - 0.55–0.74      → "shortlist"
      - 0.35–0.54      → "improve"
      - < 0.35         → "pass"
    """
    res = compute_match_score(evaluations)
    score = res["score"]
    if score >= 0.75:
        action = "interview"
    elif score >= 0.55:
        action = "shortlist"
    elif score >= 0.35:
        action = "improve"
    else:
        action = "pass"
    return {
        "action": action,
        "rationale": f"Rule-based on weighted minimum/preferred match; score={score:.2f}.",
        "details": res,
    }
