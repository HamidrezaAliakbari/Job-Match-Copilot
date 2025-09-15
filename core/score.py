from __future__ import annotations
from typing import Dict, List

def compute_match_score(evaluations: List[Dict]) -> Dict:
    """
    Weighted score:
      - For 'minimum' bucket: Met = 1.0, Partial = 0.5, Missing = 0.0
      - For 'preferred' bucket: Met = 0.5, Partial = 0.25, Missing = 0.0
    Headers are not present (filtered upstream), so denominator is total count actually scored.
    Confidence: proportion of items that had any evidence lines, clipped [0.3..0.95]
    """
    if not evaluations:
        return {"score": 0.0, "confidence": 0.4}

    weights = {
        "minimum": {"Met": 1.0, "Partial": 0.5, "Missing": 0.0},
        "preferred": {"Met": 0.5, "Partial": 0.25, "Missing": 0.0},
    }

    numer = 0.0
    denom = 0.0
    evid_cnt = 0
    for ev in evaluations:
        bucket = ev.get("bucket", "minimum")
        status = ev.get("status", "Missing")
        wmap = weights.get(bucket, weights["minimum"])
        numer += wmap.get(status, 0.0)
        denom += 1.0
        evid = ev.get("evidence") or []
        if isinstance(evid, list) and len(evid) > 0:
            evid_cnt += 1

    score = (numer / denom) if denom else 0.0
    conf = evid_cnt / denom if denom else 0.0
    # keep confidence in a pleasant range for UI
    conf = max(0.3, min(0.95, conf))
    return {"score": round(score, 2), "confidence": round(conf, 2)}
