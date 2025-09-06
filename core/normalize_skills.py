"""Skill normalisation utilities.

In a production system you would map arbitrary skill names to a well‑defined ontology such as
ESCO or O*NET.  This starter defines a small static mapping and a helper function to map any
seen skill to its canonical form.
"""

from typing import List


# Map variants to canonical names
_CANONICAL_MAP = {
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "python3": "python",
    "machine learning": "machine learning",
    "deep learning": "deep learning",
    "pandas": "pandas",
    "py torch": "pytorch",
    "tensorflow": "tensorflow",
    "sql": "sql",
}


def normalise_skill(term: str) -> str:
    """Normalise a single skill term to its canonical form."""
    t = term.lower().strip()
    return _CANONICAL_MAP.get(t, t)


def normalise_skills(skills: List[str]) -> List[str]:
    """Normalise a list of skills and remove duplicates."""
    return sorted(set(normalise_skill(s) for s in skills))