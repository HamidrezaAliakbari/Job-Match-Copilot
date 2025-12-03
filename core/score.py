# core/score.py
from __future__ import annotations
from typing import List, Dict

STATUS_WEIGHT = {
    "Met": 1.0,
    "Partial": 0.6,   # a bit more generous than 0.5
    "Partially met": 0.6,
    "Missing": 0.0,
}

TYPE_WEIGHT = {
    "required": 1.0,
    "preferred": 0.5,  # preferred counts, but half as much
}

def _ev_confidence(ev: List[str], status: str) -> float:
    """Rough confidence heuristic from evidence volume + status."""
    if status == "Met":
        return 0.9 if len(ev) >= 2 else 0.8
    if status.startswith("Partial"):
        return 0.6 if ev else 0.5
    return 0.35 if ev else 0.25

def compute_match_score(evals: List[Dict]) -> Dict:
    """
    Compute overall score in [0,1] with preferred vs required weighting and a confidence.
    """
    if not evals:
        return {"score": 0.0, "confidence": 0.5}

    num_req = sum(1 for e in evals if e.get("type") == "required")
    num_pref = sum(1 for e in evals if e.get("type") == "preferred")

    denom = (num_req * TYPE_WEIGHT["required"]) + (num_pref * TYPE_WEIGHT["preferred"])
    if denom <= 0:
        denom = len(evals)  # fallback

    total = 0.0
    confs = []

    for e in evals:
        status = e.get("status", "Missing")
        ev = e.get("evidence") or []
        etype = e.get("type", "required")
        s = STATUS_WEIGHT.get(status, 0.0)
        w = TYPE_WEIGHT.get(etype, 1.0)
        total += s * w
        confs.append(_ev_confidence(ev, status))

    score = max(0.0, min(1.0, total / denom))
    confidence = sum(confs) / len(confs) if confs else 0.6
    return {"score": round(score, 2), "confidence": round(confidence, 2)}
