# core/score.py
from __future__ import annotations
from typing import Dict, List

def compute_match_score(evaluations: List[Dict]) -> Dict[str, float]:
    """
    evaluations: list of {'requirement': str, 'status': 'Met'|'Partially met'|'Missing', 'bucket': 'minimum'|'preferred'|'other'}
    """
    weights = {"minimum": 1.0, "preferred": 0.5, "other": 0.25}
    status_val = {"Met": 1.0, "Partially met": 0.5, "Missing": 0.0}

    total_w = 0.0
    achieved = 0.0
    for ev in evaluations:
        bucket = ev.get("bucket", "minimum")
        w = weights.get(bucket, 0.5)
        total_w += w
        achieved += w * status_val.get(ev.get("status", "Missing"), 0.0)

    score = achieved / total_w if total_w > 0 else 0.0
    # simple confidence: share of items that are Met/Partial
    conf = sum(1 for e in evaluations if e.get("status") in ("Met", "Partially met")) / max(1, len(evaluations))
    return {"score": round(score, 2), "confidence": round(conf, 2)}
