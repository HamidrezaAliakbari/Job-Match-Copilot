from __future__ import annotations
from typing import Dict, List

def compute_match_score(evaluations: List[Dict]) -> Dict[str, float]:
    """
    Simple calibrated score:
      Met = 1.0
      Partial = 0.5
      Missing = 0
    score = average over requirements
    confidence trends with coverage & fraction of non-missing.
    """
    if not evaluations:
        return {"score": 0.0, "confidence": 0.5}

    total = 0.0
    non_missing = 0
    for ev in evaluations:
        st = (ev.get("status") or "").lower()
        if st == "met":
            total += 1.0
            non_missing += 1
        elif st == "partial":
            total += 0.5
            non_missing += 1
        else:
            total += 0.0

    score = total / len(evaluations)

    # confidence: higher when more items are at least Partial and evidence density is strong
    coverage = non_missing / len(evaluations)
    # clip to [0.0, 0.99]
    confidence = max(0.4, min(0.99, 0.55 + 0.4 * coverage))

    return {"score": round(score, 2), "confidence": round(confidence, 2)}
