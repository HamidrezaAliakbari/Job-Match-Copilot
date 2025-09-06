from __future__ import annotations
from typing import Dict, List, Optional

def parse_job(path: str, requirements: Optional[List[str]] = None, preferred: Optional[List[str]] = None) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    job = {
        "title": "Job",
        "requirements": requirements or [],
        "preferred": preferred or [],
        "raw_text": text,
    }
    if not job["requirements"]:
        lines = [ln.strip("-• \t") for ln in text.splitlines() if ln.strip()]
        job["requirements"] = [ln for ln in lines if len(ln) > 6][:10]
    return job
