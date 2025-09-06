from __future__ import annotations
from typing import Dict, List

def compute_match_score(evals: List[Dict]) -> Dict[str, float]:
    val = []
    for e in evals:
        if e["status"] == "Met":
            val.append(1.0)
        elif e["status"] == "Partial":
            val.append(0.5)
        else:
            val.append(0.0)
    if not val:
        return {"score": 0.0, "confidence": 0.0}
    score = sum(val) / len(val)
    met = sum(1 for e in evals if e["status"] == "Met")
    conf = min(0.95, 0.4 + 0.1 * met)
    return {"score": round(score, 2), "confidence": round(conf, 2)}
