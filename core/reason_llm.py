from __future__ import annotations
from typing import Dict, List
import re

def _normalize(s: str) -> List[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9+#.]{2,}", s.lower())]

def evaluate_requirements(requirements: List[str], resume: Dict) -> List[Dict]:
    corpus = []
    corpus += resume.get("experience_bullets", [])
    corpus += resume.get("projects", [])
    corpus += resume.get("skills", [])
    corpus = [c for c in corpus if isinstance(c, str) and c.strip()]

    results = []
    for req in requirements:
        req_toks = set(_normalize(req))
        scored = []
        for snip in corpus:
            toks = set(_normalize(snip))
            overlap = len(req_toks & toks)
            if overlap > 0:
                scored.append((overlap, snip))
        scored.sort(reverse=True, key=lambda x: x[0])
        top = [s for _, s in scored[:3]]
        if scored and scored[0][0] >= max(1, len(req_toks)//4):
            status = "Met"
        elif scored:
            status = "Partial"
        else:
            status = "Missing"
        results.append({"requirement": req, "status": status, "evidence": top})
    return results
