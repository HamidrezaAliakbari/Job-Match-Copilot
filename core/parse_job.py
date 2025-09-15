# core/parse_job.py
from typing import Dict, List, Optional
import os

from .sectionizer import split_sections, extract_job_requirements

def parse_job(
    job_path: Optional[str] = None,
    *,
    job_text: Optional[str] = None,
    requirements: Optional[List[str]] = None,
    preferred: Optional[List[str]] = None,
) -> Dict:
    """
    Return a normalized job dict:
      {
        title: str,
        requirements: List[str],
        preferred: List[str]
      }
    Priority:
      1) if job_text provided, parse it
      2) else if job_path provided, read and parse it
      3) else use passed requirements/preferred lists
    """
    if job_text is None and job_path:
        if not os.path.exists(job_path):
            raise FileNotFoundError(f"Job file not found: {job_path}")
        with open(job_path, "r", encoding="utf-8", errors="ignore") as f:
            job_text = f.read()

    title = "Job"
    reqs: List[str] = []
    prefs: List[str] = []

    if job_text:
        sections = split_sections(job_text)
        # If caller passed explicit requirements, keep them; else infer.
        reqs = requirements or extract_job_requirements(job_text)

        # Try to pull preferred from any “preferred” bucket if caller didn’t pass it
        if preferred is not None:
            prefs = preferred
        else:
            prefs = sections.get("preferred_qualifications", [])

        # Fallback if nothing in preferred and not provided
        if not prefs:
            # sometimes JDs shove “nice to have” into the same bullets; we keep reqs only
            prefs = []

        # Try to infer title from first non-empty line that’s not a header
        for ln in sections.get("body", []):
            if ln and len(ln) <= 120:
                title = ln
                break

    else:
        # No text; build from lists
        reqs = requirements or []
        prefs = preferred or []

    # Final clean
    reqs = [r for r in reqs if r and len(r) >= 2]
    prefs = [p for p in prefs if p and len(p) >= 2]

    return {
        "title": title,
        "requirements": reqs,
        "preferred": prefs,
    }
