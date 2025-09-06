from __future__ import annotations
from typing import Dict, List, Tuple
import re

# ---------------------------
# Text normalization helpers
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
# CRC clinical lexicon (synonyms)
# ---------------------------
LEX = {
    # requirement → synonyms/keywords (normalized substrings)
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
        "database search", "meSH", "endnote", "zotero"
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

# Map some common short forms to long (for evidence search)
ALIASES = {
    "crf": "case report form",
    "sdv": "source data verification",
}

# ---------------------------
# Build a searchable resume corpus (snippets + section)
# ---------------------------
def build_resume_corpus(resume: Dict) -> List[Tuple[str, str]]:
    corpus: List[Tuple[str, str]] = []

    def add_many(lines: List[str], section: str):
        for ln in lines or []:
            if ln and ln.strip():
                corpus.append((ln.strip(), section))

    if resume.get("summary"):
        # split summary into sentences-ish chunks
        summ = [s.strip() for s in re.split(r"[;\.\n]", resume["summary"]) if s.strip()]
        add_many(summ, "summary")

    add_many(resume.get("experience_bullets") or [], "experience")
    add_many(resume.get("projects") or [], "projects")
    add_many(resume.get("education") or [], "education")
    add_many(resume.get("courses") or [], "courses")

    # skills as standalone tokens
    for sk in resume.get("skills") or []:
        corpus.append((sk.strip(), "skills"))

    return corpus

# ---------------------------
# Evidence finding
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
# Main: evaluate requirements against resume
# ---------------------------
def evaluate_requirements(requirements: List[str], resume: Dict) -> List[Dict]:
    """
    Returns: List[{ requirement, status: Met|Partial|Missing, evidence: [snippets] }]
    Matching is synonym-aware (CRC lexicon) and robust to casing/punct.
    """
    corpus = build_resume_corpus(resume)
    # Precompute normalized corpus text for quick Partial signals
    corpus_text = " \n ".join([norm(s) for s, _ in corpus])

    results: List[Dict] = []

    for req in requirements:
        req_clean = req.strip()
        req_norm = norm(req_clean)

        # 1) choose lexicon entry to use (exact key match or fuzzy key by overlap)
        # try exact key
        key = None
        if req_clean.lower() in LEX:
            key = req_clean.lower()
        else:
            # fuzzy: pick the lexicon key with the largest token overlap
            tokens = set(req_norm.split())
            best_key, best_overlap = None, 0
            for k in LEX.keys():
                ov = len(tokens.intersection(set(k.split())))
                if ov > best_overlap:
                    best_key, best_overlap = k, ov
            key = best_key

        synonyms = [norm(ALIASES.get(s, s)) for s in (LEX.get(key) or [])]

        # 2) strong match → Met (evidence found)
        evidence = find_evidence(corpus, synonyms) if synonyms else []
        if evidence:
            status = "Met"
        else:
            # 3) weak/partial signals: look for any content words from the req itself
            # remove stopwords-ish short words
            req_terms = [t for t in req_norm.split() if len(t) > 3]
            weak_hit = any(t in corpus_text for t in req_terms)
            status = "Partial" if weak_hit else "Missing"

            # try to harvest evidence lines even if not matched via synonyms
            if weak_hit:
                evidence = find_evidence(corpus, req_terms)

        results.append({
            "requirement": req_clean,
            "status": status,
            "evidence": evidence,
        })

    return results
