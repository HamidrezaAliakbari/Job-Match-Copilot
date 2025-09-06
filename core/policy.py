from __future__ import annotations
from typing import Dict, Any, List

def decide_action(score: float, confidence: float, suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
    if score >= 0.75 and confidence >= 0.6:
        return {"decision": "interview", "details": {"reason": "High match & confidence"}}
    if score >= 0.55 or any(s["change_type"] == "surface_metric" for s in suggestions):
        return {
            "decision": "request-info",
            "details": {"email_draft": "Hi — I can share portfolio/code for missing areas."},
        }
    return {
        "decision": "improve",
        "details": {
            "plan": {"weeks": 2, "targets": ["Top missing skill 1", "Top missing skill 2"], "artifacts": ["Colab/GitHub demo", "Short README"]},
        },
    }
