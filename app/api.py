from __future__ import annotations
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator

from core.parse_resume import parse_resume
from core.parse_job import parse_job
from core.reason_llm import evaluate_requirements
from core.score import compute_match_score
from core.counterfactual import generate_counterfactuals
from core.action import decide_action
import re
app = FastAPI(title="Job-Match Copilot API", version="beta-02")
# ---------- Light client-side sectionizers (UI only) ----------

_WS = re.compile(r"\s+")
_BULLET = re.compile(r"^\s*(?:[-*•–]|(\d{1,3}[.)]))\s+")
_HDR_END = re.compile(r"[:：\-\s]*$")

def _n(s: str) -> str:
    return _WS.sub(" ", (s or "").strip())

def _is_resume_header(line: str) -> bool:
    h = _HDR_END.sub("", (line or "").strip()).lower()
    return h in {
        "professional summary", "summary", "objective",
        "experience", "work experience", "employment",
        "projects", "selected projects",
        "education", "academics",
        "skills", "technical skills",
        "courses", "coursework", "certifications", "certificates",
    }

def _map_resume_header(line: str) -> str:
    h = _HDR_END.sub("", (line or "").strip()).lower()
    if h in {"experience", "work experience", "employment"}:
        return "experience_bullets"
    if h in {"projects", "selected projects"}:
        return "projects"
    if h in {"education", "academics"}:
        return "education"
    if h in {"skills", "technical skills"}:
        return "skills"
    if h in {"courses", "coursework", "certifications", "certificates"}:
        return "courses"
    return "summary"

def _take_bullets(lines):
    out = []
    for ln in lines:
        if not ln: 
            continue
        if _BULLET.match(ln):
            out.append(_BULLET.sub("", ln).strip())
        else:
            out.append(ln.strip())
    return out

def sectionize_resume_ui(text: str) -> dict:
    lines = [_n(l) for l in (text or "").splitlines()]
    current = "summary"
    buckets = {
        "skills": [],
        "experience_bullets": [],
        "projects": [],
        "education": [],
        "courses": [],
    }
    summary_chunks = []

    for raw in lines:
        if not raw:
            continue
        if _is_resume_header(raw):
            current = _map_resume_header(raw)
            continue

        if current == "skills":
            for p in re.split(r"[,\u2022;|/]+", raw):
                t = p.strip()
                if t and len(t) <= 64:
                    buckets["skills"].append(t)
        elif current in buckets:
            buckets[current].append(raw)
        else:
            summary_chunks.append(raw)

    for k in ("experience_bullets", "projects", "education", "courses"):
        buckets[k] = _take_bullets(buckets[k])

    # de-dupe skills keep order
    seen, uniq = set(), []
    for s in buckets["skills"]:
        k = s.lower()
        if k and k not in seen:
            seen.add(k); uniq.append(s)
    buckets["skills"] = uniq

    return {
        "summary": " ".join(summary_chunks).strip(),
        **buckets,
    }

# ----- Job sectionizer (UI) -----
_JOB_SECTIONS = {
    "title": {"job title", "title", "position"},
    "about": {"about the role", "about the job", "role", "responsibilities", "what you’ll do", "what you will do"},
    "minimum": {"minimum qualifications", "basic qualifications", "requirements", "must have", "you have", "what you’ll need"},
    "preferred": {"preferred qualifications", "nice to have", "bonus", "good to have", "strongly preferred"},
}

def _which_job_header(line: str):
    h = _HDR_END.sub("", (line or "").strip()).lower()
    for b, names in _JOB_SECTIONS.items():
        if h in names:
            return b
    return None

def sectionize_job_ui(text: str, explicit_requirements=None, explicit_preferred=None) -> dict:
    if explicit_requirements or explicit_preferred:
        return {
            "title": "",
            "requirements": list(dict.fromkeys(explicit_requirements or [])),
            "preferred": list(dict.fromkeys(explicit_preferred or [])),
        }

    lines = [_n(l) for l in (text or "").splitlines()]
    bucket = None
    title = ""
    reqs, prefs, buf = [], [], []

    def flush(into):
        if not buf:
            return
        merged = " ".join(buf).strip()
        buf.clear()
        if not merged:
            return
        parts = [p.strip() for p in re.split(r"[•;]\s+|\n", merged) if p.strip()]
        into.extend(parts or [merged])

    for raw in lines:
        if not raw:
            continue
        hdr = _which_job_header(raw)
        if hdr:
            if bucket == "minimum": flush(reqs)
            if bucket == "preferred": flush(prefs)
            bucket = hdr
            continue

        if bucket == "title" and not title:
            title = raw
            continue

        if bucket == "minimum":
            if _BULLET.match(raw): reqs.append(_BULLET.sub("", raw).strip())
            else: buf.append(raw)
            continue

        if bucket == "preferred":
            if _BULLET.match(raw): prefs.append(_BULLET.sub("", raw).strip())
            else: buf.append(raw)
            continue
        # ignore "about" for scoring

    if bucket == "minimum": flush(reqs)
    if bucket == "preferred": flush(prefs)

    # strip any surviving header-ish lines
    header_like = {h for names in _JOB_SECTIONS.values() for h in names}
    reqs = [r for r in reqs if _HDR_END.sub("", r).lower() not in header_like]
    prefs = [r for r in prefs if _HDR_END.sub("", r).lower() not in header_like]

    # de-dupe keep order
    reqs = list(dict.fromkeys(reqs))
    prefs = list(dict.fromkeys(prefs))

    return {"title": title, "requirements": reqs, "preferred": prefs}

# --------- Models ----------
class ResumeObj(BaseModel):
    summary: Optional[str] = ""
    skills: Optional[List[str]] = []
    experience_bullets: Optional[List[str]] = []
    projects: Optional[List[str]] = []
    education: Optional[List[str]] = []
    courses: Optional[List[str]] = []

class JobObj(BaseModel):
    title: Optional[str] = "Job"
    requirements: Optional[List[str]] = []
    preferred: Optional[List[str]] = []

class ScoreRequest(BaseModel):
    resume: Optional[ResumeObj] = None
    job: Optional[JobObj] = None
    resume_path: Optional[str] = None
    job_path: Optional[str] = None
    # legacy convenience fields (UI often posts plain text)
    resume_text: Optional[str] = None
    job_text: Optional[str] = None
    # optional explicit lists (overrides extracted ones)
    requirements: Optional[List[str]] = None
    preferred: Optional[List[str]] = None

    @validator("*", pre=True)
    def _strip_none(cls, v):
        return v

def _resolve_resume(req: ScoreRequest) -> Dict:
    if req.resume:
        return req.resume.model_dump()
    # allow text > parse
    if req.resume_text or req.resume_path:
        return parse_resume(req.resume_path, text=req.resume_text)
    raise HTTPException(status_code=422, detail="Provide resume or resume_path or resume_text")

def _resolve_job(req: ScoreRequest) -> Dict:
    if req.job and (req.job.requirements or req.job.preferred):
        # explicit object wins, but ensure headers are stripped by parser
        return parse_job(text="\n".join((req.job.requirements or []) + (req.job.preferred or [])),
                         requirements=req.job.requirements,
                         preferred=req.job.preferred)
    if req.job_text or req.job_path:
        return parse_job(req.job_path, text=req.job_text,
                         requirements=req.requirements, preferred=req.preferred)
    # final fallback: if caller only provided explicit arrays
    if req.requirements or req.preferred:
        return parse_job(text="\n".join((req.requirements or []) + (req.preferred or [])),
                         requirements=req.requirements, preferred=req.preferred)
    raise HTTPException(status_code=422, detail="Provide job or job_path or job_text or explicit requirements")

# --------- Health ----------
@app.get("/healthz")
def healthz():
    return {"ok": True}

# --------- Score ----------
@app.post("/score")
def score_match(request: ScoreRequest):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        evals = evaluate_requirements(job.get("requirements") or [], resume,
                                      preferred=job.get("preferred") or [])
        agg = compute_match_score(evals)
        return {**agg, "evaluations": evals}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/score failed: {e}")

# --------- Counterfactual ----------
@app.post("/counterfactual")
def counterfactual(request: ScoreRequest):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        suggestions = generate_counterfactuals(resume, job)
        return {"suggestions": suggestions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/counterfactual failed: {e}")

# --------- Action ----------
@app.post("/action")
def action(request: ScoreRequest):
    try:
        resume = _resolve_resume(request)
        job = _resolve_job(request)
        evals = evaluate_requirements(job.get("requirements") or [], resume,
                                      preferred=job.get("preferred") or [])
        decision = decide_action(evals)
        return decision
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/action failed: {e}")
