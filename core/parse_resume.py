# core/parse_resume.py
from typing import Dict, List, Optional
import os
from .sectionizer import split_sections, coalesce_bullets

def _first_n(items: List[str], n: int) -> List[str]:
    return items[:n] if items else []

def parse_resume(resume_path: Optional[str] = None, *, resume_text: Optional[str] = None) -> Dict:
    """
    Return a normalized resume dict:
      {
        skills: List[str],
        experience_bullets: List[str],
        projects: List[str],
        education: List[str],
        courses: List[str]
      }
    Uses sectionizer to avoid treating section headers as bullets.
    """
    if resume_text is None and resume_path:
        if not os.path.exists(resume_path):
            raise FileNotFoundError(f"Resume file not found: {resume_path}")
        with open(resume_path, "r", encoding="utf-8", errors="ignore") as f:
            resume_text = f.read()

    if not resume_text:
        # minimal empty skeleton
        return {
            "skills": [],
            "experience_bullets": [],
            "projects": [],
            "education": [],
            "courses": [],
        }

    sections = split_sections(resume_text)

    # Pull by canonical keys; fall back to body
    skills = sections.get("skills", [])
    experience = sections.get("experience", []) or sections.get("body", [])
    projects = sections.get("projects", [])
    education = sections.get("education", [])
    courses = sections.get("courses", [])

    # Safety: ensure content is bullet-like and headers are already stripped
    experience = coalesce_bullets(experience)
    projects = coalesce_bullets(projects)
    education = coalesce_bullets(education)
    courses = coalesce_bullets(courses)

    return {
        "skills": _first_n(skills, 50),
        "experience_bullets": _first_n(experience, 200),
        "projects": _first_n(projects, 100),
        "education": _first_n(education, 100),
        "courses": _first_n(courses, 100),
    }
