# core/reason_llm.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import re

# ---------------------------
# Normalization helpers
# ---------------------------
_ws = re.compile(r"\s+")
_punct = re.compile(r"[^\w\s]+")

def norm(s: str) -> str:
    s = s.lower()
    s = _punct.sub(" ", s)
    s = _ws.sub(" ", s).strip()
    return s

def tokens(s: str) -> List[str]:
    return [t for t in norm(s).split() if t]

def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb: 
        return 0.0
    return len(sa & sb) / len(sa | sb)

# ---------------------------
# Heuristics & lexicons
# ---------------------------
HEADER_LINES = {
    "summary","professional summary","experience","work experience","employment",
    "projects","project","education","skills","certifications","publications",
    "about the role","responsibilities","minimum qualifications","preferred qualifications",
    "requirements","job title","objective"
}

# CRC / ML-ish synonyms (normalized substrings)
LEX: Dict[str, List[str]] = {
    "python": ["python"],
    "fastapi": ["fastapi"],
    "aws": ["aws","amazon web services","ecs","fargate","s3","ec2","lambda"],
    "scikit-learn": ["scikit learn","sklearn","scikit-learn"],
    "pytorch": ["pytorch","torch"],
    "tensorflow": ["tensorflow","tf","keras"],
    "docker": ["docker","container"],
    "kubernetes": ["kubernetes","k8s"],
    "ci/cd": ["ci cd","ci/cd","continuous integration","continuous delivery","github actions","gitlab ci"],
    "hipaa": ["hipaa","phi","protected health information"],
    "irb": ["irb","institutional review board","human subjects"],
    "data visualization": ["data visualization","dash","plotly","power bi","tableau","matplotlib","seaborn"],
    # degrees
    "master’s degree": ["masters degree","master s degree","ms degree","m s","m.sc","msc","master of science"],
    "bachelor’s degree": ["bachelors degree","bachelor s degree","bs degree","b s","b.sc","bsc","undergraduate"],
    # frameworks / api
    "api deployment": ["deploy api","rest api","production api","uvicorn","gunicorn"],
}

ALIASES = {
    "sklearn": "scikit-learn",
    "ci cd": "ci/cd",
    "ms": "master’s degree",
    "bs": "bachelor’s degree",
}

def to_lex_key(req: str) -> Optional[str]:
    """Pick a lexicon key by max token overlap."""
    rq = norm(req)
    rq_t = set(tokens(rq))
    best, score = None, 0
    for k in LEX.keys():
        ov = len(rq_t & set(k.split()))
        if ov > score:
            best, score = k, ov
    return best

# ---------------------------
# Build resume corpus (line, section)
# ---------------------------
def build_resume_corpus(resume: Dict) -> List[Tuple[str, str]]:
    corpus: List[Tuple[str, str]] = []

    def add_many(lines: List[str], section: str):
        for ln in lines or []:
            if not ln: 
                continue
            ln_clean = ln.strip()
            # Drop pure headers
            if norm(ln_clean) in HEADER_LINES:
                continue
            # Keep lines that carry signal
            if len(ln_clean) >= 2:
                corpus.append((ln_clean, section))

    if resume.get("summary"):
        # split summary into sentence-like chunks
        summ = [s.strip() for s in re.split(r"[.\n;]", resume["summary"]) if s.strip()]
        add_many(summ, "summary")

    add_many(resume.get("experience_bullets") or [], "experience")
    add_many(resume.get("projects") or [], "projects")
    add_many(resume.get("education") or [], "education")
    add_many(resume.get("courses") or [], "courses")

    # skills as atomic entries
    for sk in resume.get("skills") or []:
        s = sk.strip()
        if s and norm(s) not in HEADER_LINES:
            corpus.append((s, "skills"))

    return corpus

# ---------------------------
# Evidence search
# ---------------------------
def _needle_list(req: str) -> List[str]:
    """Build prioritized needle list: (synonyms -> exact phrases -> content words)."""
    needles: List[str] = []
    # 1) synonyms
    key = to_lex_key(req) or req.lower()
    syns = LEX.get(key, [])
    needles.extend([norm(ALIASES.get(s, s)) for s in syns])
    # 2) exact normalized phrase
    rq_norm = norm(req)
    if rq_norm and rq_norm not in needles:
        needles.append(rq_norm)
    # 3) salient content words (length >= 3)
    words = [w for w in rq_norm.split() if len(w) >= 3]
    for w in words:
        if w not in needles:
            needles.append(w)
    return needles

def _match_strength(snip: str, needles: List[str]) -> float:
    """Score evidence strength for a single snippet."""
    n_snip = norm(snip)
    # exact full-phrase match is strongest
    full_phrases = [n for n in needles if " " in n]
    for p in full_phrases:
        if p in n_snip:
            return 1.0
    # strong token overlap
    overlap = jaccard(tokens(n_snip), [t for n in needles for t in n.split()])
    if overlap >= 0.45:
        return 0.75
    # any keyword hit
    if any(n in n_snip for n in needles):
        return 0.55
    return 0.0

def find_evidence(corpus: List[Tuple[str, str]], req: str, k: int = 3) -> List[str]:
    needles = _needle_list(req)
    scored: List[Tuple[float, str]] = []
    for snip, section in corpus:
        # downweight if the line looks like a header inside corpus (paranoia)
        is_headerish = norm(snip) in HEADER_LINES
        base = _match_strength(snip, needles)
        if base <= 0:
            continue
        if is_headerish:
            base *= 0.5
        # Slight boost if from experience/projects (vs. skills-only)
        if section in {"experience", "projects"}:
            base += 0.05
        scored.append((base, snip))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [snip for _, snip in scored[:k]]

# ---------------------------
# Degree helpers (tiny)
# ---------------------------
DEGREE_PATTERNS = {
    "master’s degree": re.compile(r"\b(masters?|m\.?s\.?|msc|master of science)\b", re.I),
    "bachelor’s degree": re.compile(r"\b(bachelors?|b\.?s\.?|bsc|bachelor of science)\b", re.I),
}

def has_degree(resume: Dict, degree_key: str) -> bool:
    pat = DEGREE_PATTERNS.get(degree_key)
    if not pat:
        return False
    for line in (resume.get("education") or []):
        if pat.search(line):
            return True
    # sometimes degree mentioned in summary/experience
    for blk in (resume.get("experience_bullets") or []) + ([resume.get("summary")] if resume.get("summary") else []):
        if blk and pat.search(blk):
            return True
    return False

# ---------------------------
# Main API
# ---------------------------
def evaluate_requirements(requirements: List[str], resume: Dict, preferred: Optional[List[str]] = None) -> List[Dict]:
    """
    Returns list of:
    {
      "requirement": str,
      "status": "Met"|"Partial"|"Missing",
      "evidence": [str, ...],
      "type": "required"|"preferred"
    }
    """
    preferred = preferred or []
    corpus = build_resume_corpus(resume)
    corpus_text = " \n ".join([norm(s) for s, _ in corpus])

    out: List[Dict] = []

    def eval_one(req: str, req_type: str) -> Dict:
        req_clean = req.strip()
        # degree shortcuts
        key = to_lex_key(req_clean) or ""
        if key in ("master’s degree", "bachelor’s degree"):
            have = has_degree(resume, key)
            return {
                "requirement": req_clean,
                "status": "Met" if have else "Missing",
                "evidence": [e for e in (resume.get("education") or []) if e][:2] if have else [],
                "type": req_type,
            }

        ev = find_evidence(corpus, req_clean)
        if ev:
            status = "Met"
        else:
            # weak signal = any content term shows up
            req_terms = [t for t in tokens(req_clean) if len(t) >= 4]
            weak = any(t in corpus_text for t in req_terms)
            status = "Partial" if weak else "Missing"
            if weak:
                # harvest a couple weak lines to show why partial
                ev = find_evidence(corpus, " ".join(req_terms))[:2]

        return {"requirement": req_clean, "status": status, "evidence": ev, "type": req_type}

    for r in requirements or []:
        if r and norm(r) not in HEADER_LINES:
            out.append(eval_one(r, "required"))
    for r in preferred or []:
        if r and norm(r) not in HEADER_LINES:
            out.append(eval_one(r, "preferred"))

    return out
