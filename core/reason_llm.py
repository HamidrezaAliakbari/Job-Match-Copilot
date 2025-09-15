from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import re

# ---------------------------
# Text normalization helpers (unchanged)
# ---------------------------
_ws = re.compile(r"\s+")
_punct = re.compile(r"[^\w\s]+")

def norm(s: str) -> str:
    s = s.lower()
    s = _punct.sub(" ", s)
    s = _ws.sub(" ", s).strip()
    return s

def contains_any(hay: str, needles: List[str]) -> bool:
    low = norm(hay)
    return any(n in low for n in needles)

def any_in_any(snips: List[str], needles: List[str]) -> bool:
    for s in snips:
        if contains_any(s, needles):
            return True
    return False

# ---------------------------
# Header detection (NEW)
# ---------------------------
BULLET_RE = re.compile(r"^\s*(?:[-*•–]|(\d+[\.\)]))\s+")
HEADER_LINE_RE = re.compile(r"^\s*[A-Za-z].{0,80}:?\s*$")

HEADER_ALIASES = [
    r"minimum\s+qualifications?",
    r"basic\s+qualifications?",
    r"preferred\s+qualifications?",
    r"nice\s*to\s*have",
    r"responsibilit(y|ies)",
    r"about\s+the\s+(job|role|team|company)",
    r"duties",
    r"requirements?",
    r"description",
    r"overview",
]

def _looks_like_header(ln: str) -> bool:
    if not ln:
        return False
    if BULLET_RE.match(ln):
        return False
    low = ln.lower().rstrip(":").strip()
    if HEADER_LINE_RE.match(ln) and (ln.endswith(":") or len(low.split()) <= 6):
        return True
    for p in HEADER_ALIASES:
        if re.fullmatch(p, low):
            return True
    return False

# ---------------------------
# CRC clinical lexicon (yours, unchanged)
# ---------------------------
LEX = {
    "collects & organizes patient data": [
        "chart abstraction", "data collection", "collect data", "patient data",
        "ehr", "emr", "redcap", "electronic data capture", "edc", "data entry"
    ],
    "maintains records and databases": [
        "database", "records management", "redcap", "lims", "excel", "access",
        "data quality", "data integrity", "data cleaning"
    ],
    "uses software programs to generate graphs and reports": [
        "graphs", "reports", "tableau", "power bi", "excel charts", "matplotlib",
        "seaborn", "reporting", "visualization", "r markdown", "spss", "stata"
    ],
    "managing the recruitment, screening, and enrollment of research patients": [
        "recruit", "recruitment", "screen", "screening", "prescreen", "enroll",
        "enrollment", "eligibility", "inclusion criteria", "exclusion criteria",
        "study visits", "participant outreach"
    ],
    "obtains patient study data from medical records, physicians, etc.": [
        "ehr", "emr", "medical records", "chart review", "physician notes",
        "epic", "cerner"
    ],
    "conducts library searches": [
        "pubmed", "google scholar", "systematic review", "literature review",
        "database search", "mesh", "endnote", "zotero"
    ],
    "verifies accuracy of study forms": [
        "case report form", "crf", "source data verification", "sdv",
        "data verification", "quality check", "qa qc", "query resolution"
    ],
    "updates study forms per protocol": [
        "protocol", "crf", "case report form", "study amendment", "version control"
    ],
    "documents patient visits and procedures": [
        "document visit", "visit notes", "procedure note", "source documentation",
        "clinic visit", "follow up visit", "study visit"
    ],
    "assists with regulatory binders and qa/qc procedures": [
        "regulatory binder", "essential documents", "delegation log", "training log",
        "qa qc", "quality assurance", "monitoring visit", "audit"
    ],
    "assists with interviewing study subjects": [
        "interview participants", "semi structured interview", "qualitative",
        "survey administration", "questionnaire administration"
    ],
    "administers psychiatric assessments and scores questionnaires": [
        "phq 9", "gad 7", "ham d", "ham a", "bdi", "bai", "assessment battery",
        "validated questionnaires", "scoring"
    ],
    "provides basic explanation of study and in some cases obtains informed consent from": [
        "informed consent", "consenting", "consent form", "assent"
    ],
    "performs study procedures, which may include neuromodulation (tms and tes, training will be offered by study team), phlebotomy (a course is offered at umn), etc.": [
        "tms", "transcranial magnetic", "t es", "tes", "neuromodulation",
        "eeg", "mri", "phlebotomy", "blood draw", "venipuncture"
    ],
    "assists with study regulatory submissions": [
        "irb submission", "continuing review", "amendment", "adverse event report",
        "protocol deviation", "redaction", "consent template"
    ],
    "ensuring compliance with the umn irb and other federal and institutional guidelines": [
        "irb", "hipaa", "gcp", "citi training", "regulatory compliance"
    ],
    "writes consent forms": [
        "consent template", "consent form drafting", "icf", "consent language"
    ],
    "verifies subject inclusion/exclusion criteria": [
        "eligibility", "inclusion criteria", "exclusion criteria", "pre screen"
    ],
    "periodic special projects, such as a grant submission or a journal article submission": [
        "grant submission", "nih", "nsf", "manuscript", "journal submission",
        "coauthor", "first author", "conference abstract"
    ],
    "performs administrative support duties as required": [
        "scheduling", "calendar", "email correspondence", "procurement", "ordering",
        "meeting minutes", "documentation"
    ],
}

ALIASES = {
    "crf": "case report form",
    "sdv": "source data verification",
}

# ---------------------------
# Build a searchable resume corpus (unchanged)
# ---------------------------
def build_resume_corpus(resume: Dict) -> List[Tuple[str, str]]:
    corpus: List[Tuple[str, str]] = []

    def add_many(lines: List[str], section: str):
        for ln in lines or []:
            if ln and ln.strip():
                corpus.append((ln.strip(), section))

    if resume.get("summary"):
        summ = [s.strip() for s in re.split(r"[;\.\n]", str(resume["summary"])) if s.strip()]
        add_many(summ, "summary")

    add_many(resume.get("experience_bullets") or [], "experience")
    add_many(resume.get("projects") or [], "projects")
    add_many(resume.get("education") or [], "education")
    add_many(resume.get("courses") or [], "courses")

    for sk in resume.get("skills") or []:
        corpus.append((str(sk).strip(), "skills"))

    return corpus

# ---------------------------
# Evidence finding (unchanged)
# ---------------------------
def find_evidence(corpus: List[Tuple[str, str]], needles: List[str]) -> List[str]:
    out: List[str] = []
    for snip, _sec in corpus:
        n = norm(snip)
        if any(ned in n for ned in needles):
            out.append(snip)
            if len(out) >= 3:
                break
    return out

# ---------------------------
# Main: evaluate (enhanced, but backward-compatible)
# ---------------------------
def evaluate_requirements(
    requirements: List[str],
    resume: Dict,
    preferred: Optional[List[str]] = None
) -> List[Dict]:
    """
    Returns: [{'requirement', 'status': 'Met'|'Partial'|'Missing', 'evidence': [...], 'bucket': 'minimum'|'preferred'}]
    - Skips obvious section headers so they are never scored.
    - Tags each requirement with a bucket; 'preferred' is down-weighted later in scoring.
    """
    preferred = preferred or []
    corpus = build_resume_corpus(resume)
    corpus_text = " \n ".join([norm(s) for s, _ in corpus])

    def eval_one(req: str) -> Dict:
        req_clean = (req or "").strip()
        if not req_clean or _looks_like_header(req_clean):
            # treat header-like strings as non-scorable; mark Missing with no penalty later via bucket if you prefer
            return {"requirement": req_clean, "status": "Missing", "evidence": []}

        req_norm = norm(req_clean)

        # pick lexicon entry (exact match or fuzzy overlap)
        key = None
        if req_clean.lower() in LEX:
            key = req_clean.lower()
        else:
            tokens = set(req_norm.split())
            best_key, best_overlap = None, 0
            for k in LEX.keys():
                ov = len(tokens.intersection(set(k.split())))
                if ov > best_overlap:
                    best_key, best_overlap = k, ov
            key = best_key

        synonyms = [norm(ALIASES.get(s, s)) for s in (LEX.get(key) or [])]

        evidence = find_evidence(corpus, synonyms) if synonyms else []
        if evidence:
            status = "Met"
        else:
            # weak match with content terms (ignore very short tokens)
            req_terms = [t for t in req_norm.split() if len(t) > 3]
            weak_hit = any(t in corpus_text for t in req_terms)
            status = "Partial" if weak_hit else "Missing"
            if weak_hit and not evidence:
                evidence = find_evidence(corpus, req_terms)

        return {"requirement": req_clean, "status": status, "evidence": evidence}

    results: List[Dict] = []

    # Minimum bucket
    for r in (requirements or []):
        rec = eval_one(r)
        rec["bucket"] = "minimum"
        results.append(rec)

    # Preferred bucket
    for r in (preferred or []):
        rec = eval_one(r)
        rec["bucket"] = "preferred"
        results.append(rec)

    return results
