# ui/streamlit_app.py
import os
import re
import json
from typing import Any, Dict, List, Optional, Union

import requests
import streamlit as st


# ----------------- Demo fixtures (copy/paste-friendly) -----------------
DEMO_RESUME = """Summary
Data Scientist with 2 years of experience building predictive models and analytics solutions. Skilled in Python, SQL, and scikit-learn. Strong problem-solving skills and experience working with cross-functional teams.

Education
B.S. Computer Science — University of Illinois (2021)

Projects
- Predictive Maintenance: Developed a machine learning model in Python to predict equipment failures, reducing downtime by 20%.
- Web Analytics Dashboard: Built an interactive dashboard using Dash to visualize user engagement metrics.
- Customer Segmentation: Used clustering methods in scikit-learn to identify customer groups for targeted marketing.

Experience
Data Scientist — Analytics Solutions Inc. (2022–present)
- Built regression and classification models using scikit-learn and pandas.
- Designed SQL queries and optimized pipelines for large-scale datasets.
- Collaborated with stakeholders to deliver data-driven insights.

Intern — Software Engineering (2021)
- Assisted in developing REST APIs using Flask.
- Wrote unit tests and performed code reviews.

Skills
Python, scikit-learn, SQL, Flask, Pandas, Data Visualization
"""

DEMO_JOB = """Job Title: Machine Learning Engineer — Healthcare AI

About the Role:
We are seeking a motivated Machine Learning Engineer to join our healthcare AI team. This role involves developing, deploying, and maintaining machine learning models for clinical decision support and biomedical signal analysis.

Minimum Qualifications:
- Bachelor’s degree in Computer Science, Electrical Engineering, or related field
- Proficiency in Python for ML development
- Experience with FastAPI or Flask for APIs
- Hands-on experience with AWS or other cloud platforms
- Strong communication and teamwork

Preferred Qualifications:
- Master’s degree in ML, AI, or related field
- Experience with CI/CD pipelines and containerization (Docker, Kubernetes)
- Familiarity with HIPAA / IRB compliance for healthcare data
- Publications in ML/AI or healthcare journals/conferences
- Data visualization (Tableau, Power BI, matplotlib, or seaborn)
"""

DEMO_REQS = ""


# ----------------- helpers: safe secrets/env -----------------
def safe_secret(key: str, default=None):
    try:
        return st.secrets.get(key, os.environ.get(key, default))  # type: ignore[attr-defined]
    except Exception:
        return os.environ.get(key, default)


# ----------------- configuration -----------------
st.set_page_config(page_title="Job-Match Copilot — UI", layout="wide")
st.title("💼 Job-Match Copilot (Render UI)")

DEBUG = (safe_secret("DEBUG", "0") == "1")
API_BASE = safe_secret("API_BASE", None)  # e.g. https://job-match-copilot-api.onrender.com

API_PROTECT_HEADER = safe_secret("API_PROTECT_HEADER", "X-Render-Secret")
API_PROTECT_TOKEN  = safe_secret("RENDER_API_SECRET", None)

# URL query param toggle for demo fill (no session_state needed)
qp = st.query_params
DEMO_FLAG = qp.get("demo", ["0"])[0] if hasattr(qp, "get") else (st.experimental_get_query_params().get("demo", ["0"])[0] if hasattr(st, "experimental_get_query_params") else "0")
IS_DEMO = (DEMO_FLAG == "1")

# Allow overriding base in sidebar in DEBUG mode
if DEBUG:
    st.sidebar.caption("API base (debug)")
    api_base = st.sidebar.text_input("Base URL", value=(API_BASE or "http://127.0.0.1:8000")).rstrip("/")
else:
    api_base = (API_BASE or "").rstrip("/")

if not api_base:
    st.error(
        "API_BASE is not configured. Set it as an Environment Variable on this UI service.\n\n"
        "Example value: https://job-match-copilot-api.onrender.com"
    )
    st.stop()

# ----------------- sidebar: health & credits -----------------
def _auth_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if API_PROTECT_TOKEN:
        headers[API_PROTECT_HEADER] = API_PROTECT_TOKEN
    return headers

if st.sidebar.button("Check API health"):
    try:
        r = requests.get(f"{api_base}/healthz", headers=_auth_headers(), timeout=10)
        r.raise_for_status()
        st.sidebar.success(r.json())
    except Exception as e:
        st.sidebar.error(f"Health failed: {e}")

st.sidebar.caption(f"API: {api_base}")
st.sidebar.markdown(
    '[Developed by Hamidreza Aliakbari](https://www.linkedin.com/in/hamidreza-aliakbarikhouei-a04727190/)',
)

# ----------------- inputs -----------------
left, right = st.columns(2)

with left:
    st.subheader("Resume")
    resume_text = st.text_area(
        "Paste resume text (recommended on cloud)",
        value=(DEMO_RESUME if IS_DEMO else ""),
        placeholder="Paste the resume text here…",
        height=220,
    )
    resume_path = st.text_input(
        "…or a resume file path (local dev only)",
        placeholder="e.g., data/samples/resume_sample.md",
        value="",
    )

with right:
    st.subheader("Job")
    job_text = st.text_area(
        "Paste job description (recommended on cloud)",
        value=(DEMO_JOB if IS_DEMO else ""),
        placeholder="Paste the job description here…",
        height=220,
    )
    job_path = st.text_input(
        "…or a job file path (local dev only)",
        placeholder="e.g., data/samples/job_sample.md",
        value="",
    )

st.markdown("---")

req_csv = st.text_input(
    "Explicit requirements (comma-separated — optional)",
    value=(DEMO_REQS if IS_DEMO else "Python, FastAPI, AWS"),
    help="If provided, they are sent as 'requirements'. Leave blank to let the backend infer.",
)
requirements = [r.strip() for r in req_csv.split(",") if r.strip()]


# ----------------- minimal parsing helpers (safe for demo) -----------------
_BULLET_RE = re.compile(r"^\s*([\-*•–]|(\d+\.)|(\d+\)))\s+")

def _extract_bullets(text: str, max_items: int = 20) -> List[str]:
    lines = [ln.strip() for ln in text.splitlines()]
    items: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if _BULLET_RE.match(ln) or ";" in ln:
            parts = [p.strip(" •*-–\t") for p in re.split(r"[;•]", ln) if p.strip()]
            for p in parts:
                if 2 <= len(p) <= 300:
                    items.append(p)
        else:
            if 2 <= len(ln) <= 300:
                items.append(ln)
        if len(items) >= max_items:
            break
    if not items and text.strip():
        items = [text.strip()]
    return items

def _guess_skills_from_text(text: str, max_items: int = 15) -> List[str]:
    skills: List[str] = []
    for ln in text.splitlines()[:10]:
        if "skill" in ln.lower() or "," in ln or ";" in ln:
            parts = re.split(r"[,\u2022;|/]+", ln)
            for p in parts:
                t = p.strip()
                if 1 < len(t) <= 32 and any(ch.isalpha() for ch in t):
                    if " " in t and len(t.split()) > 4:
                        continue
                    skills.append(t)
    seen = set()
    out: List[str] = []
    for s in skills:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
        if len(out) >= max_items:
            break
    return out

def _extract_requirements(text: str, max_items: int = 30) -> List[str]:
    items = _extract_bullets(text, max_items=max_items)
    items = [it for it in items if 2 <= len(it) <= 300]
    if not items and text.strip():
        items = [text.strip()]
    return items[:max_items]


# ----------------- payload builders -----------------
def _dedupe_preserve(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        t = (it or "").strip()
        if not t:
            continue
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


def build_payload() -> Dict[str, Any]:
    """
    EXACT structure:
    {
      "requirements": [...],           # explicit requirements from the UI box
      "resume": {...},                 # sectionized resume or resume_path
      "job": { "title":..., "requirements":[...], "preferred":[...] }  # job text/paths
    }

    Change requested: also append the explicit requirements into job.requirements.
    """
    payload: Dict[str, Any] = {}

    # ---- TOP-LEVEL EXPLICIT REQUIREMENTS (keep exactly as user wants) ----
    explicit_reqs = [r.strip() for r in requirements if r.strip()]
    if explicit_reqs:
        payload["requirements"] = explicit_reqs

    # ---- RESUME ----
    if resume_text.strip():
        payload["resume"] = {
            "summary": _extract_summary(resume_text),
            "skills": _guess_skills_from_text(resume_text),
            "experience_bullets": _extract_experience(resume_text),
            "projects": _extract_projects(resume_text),
            "education": _extract_education(resume_text),
            "courses": _extract_courses(resume_text),
        }
    elif resume_path.strip():
        payload["resume"] = {}  # keep key present like your example
        payload["resume_path"] = resume_path.strip()

    # ---- JOB ----
    job_obj: Dict[str, Any] = {"title": "", "requirements": [], "preferred": []}

    if job_text.strip():
        title, mins, prefs = sectionize_job(job_text)
        job_obj["title"] = title or ""
        job_obj["requirements"] = mins or []
        job_obj["preferred"] = prefs or []
    elif job_path.strip():
        payload["job_path"] = job_path.strip()

    # Append explicit requirements into job.requirements (dedupe, preserve order)
    if explicit_reqs:
        job_obj["requirements"] = _dedupe_preserve(list(job_obj.get("requirements", [])) + explicit_reqs)

    # Only include the job object if it has any content or we injected explicit reqs
    if job_obj.get("title") or job_obj.get("requirements") or job_obj.get("preferred"):
        payload["job"] = job_obj
    else:
        # still include an empty job object to match your example structure if you prefer:
        payload["job"] = {"title": "", "requirements": explicit_reqs or [], "preferred": []}

    # Return as-is (do NOT drop top-level "requirements"; user asked to keep it)
    return payload



# --- tiny sectionizers (resume) ---
def _extract_summary(text: str) -> str:
    # take first non-empty block above "Education" or "Experience"
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    for b in blocks:
        if re.search(r"^(summary|professional summary)\b", b, re.I):
            return " ".join(b.splitlines()[1:]).strip() or b
    # fallback: first block
    return blocks[0] if blocks else ""

def _extract_education(text: str) -> List[str]:
    return _extract_section_lines(text, r"(education|academics)")

def _extract_projects(text: str) -> List[str]:
    return _extract_section_lines(text, r"(projects|project experience)")

def _extract_experience(text: str) -> List[str]:
    return _extract_section_lines(text, r"(experience|work experience|employment)")

def _extract_courses(text: str) -> List[str]:
    return _extract_section_lines(text, r"(courses|relevant coursework)")

def _extract_section_lines(text: str, header_regex: str) -> List[str]:
    # split by headers; capture lines under the header until next header
    lines = text.splitlines()
    out: List[str] = []
    capture = False
    header = re.compile(rf"^\s*{header_regex}\s*$", re.I)
    any_header = re.compile(r"^\s*(summary|professional summary|education|academics|projects|project experience|experience|work experience|employment|skills|courses|relevant coursework)\s*$", re.I)
    for ln in lines:
        if header.match(ln):
            capture = True
            continue
        if capture and any_header.match(ln):
            break
        if capture:
            s = ln.strip(" •*-–\t")
            if s:
                out.append(s)
    # clean bullets
    out = _extract_bullets("\n".join(out), max_items=50)
    return out

# --- sectionizer (job) ---
HEADER_MIN  = re.compile(r"^\s*(minimum qualifications?|basic qualifications?)\s*:?$", re.I)
HEADER_PREF = re.compile(r"^\s*(preferred|preferred qualifications?)\s*:?$", re.I)
HEADER_TITLE= re.compile(r"^\s*(job title|title)\s*:?$", re.I)
HEADER_ABOUT= re.compile(r"^\s*(about|about the role)\s*:?$", re.I)
HEADER_ANY  = re.compile(r"^\s*(about|about the role|job title|title|min(imum)?\s+qualifications?|basic\s+qualifications?|preferred(\s+qualifications?)?)\s*:?$", re.I)

def sectionize_job(text: str) -> (str, List[str], List[str]):
    title = ""
    mins: List[str] = []
    prefs: List[str] = []
    cur = None
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if HEADER_TITLE.match(ln):
            cur = "title";  # next non-empty becomes title
            continue
        if HEADER_MIN.match(ln):
            cur = "min"; continue
        if HEADER_PREF.match(ln):
            cur = "pref"; continue
        if HEADER_ABOUT.match(ln):
            cur = "about"; continue

        if cur == "title" and not HEADER_ANY.match(ln):
            title = ln
            cur = None
            continue

        if cur in ("min", "pref"):
            if not HEADER_ANY.match(ln):
                cleaned = ln.lstrip("-•*– ").strip()
                if cleaned:
                    (mins if cur == "min" else prefs).append(cleaned)
            continue

    # fallback: if nothing captured, treat bullet-looking lines as mins
    if not mins:
        mins = _extract_requirements(text, max_items=30)
        # strip section headers that slipped in
        mins = [m for m in mins if not HEADER_ANY.match(m)]
    return title, mins, prefs


# ----------------- HTTP -----------------
def post_json(path: str, body: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    url = f"{api_base}{path}"
    r = requests.post(url, json=body, headers=_auth_headers(), timeout=timeout)
    r.raise_for_status()
    return r.json()


# ----------------- buttons -----------------
b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
score_clicked = b1.button("Ingest & Score", type="primary", use_container_width=True)
counter_clicked = b2.button("Counterfactuals", use_container_width=True)
action_clicked = b3.button("Action", use_container_width=True)

# NEW: Demo fill button right beside the others (no session_state)
def _set_demo(flag: bool):
    try:
        # New API (Streamlit >= 1.32)
        st.query_params.update({"demo": "1" if flag else "0"})
    except Exception:
        # Fallback for older versions
        st.experimental_set_query_params(demo="1" if flag else "0")
    st.rerun()

if b4.button("🔁 Load Demo", use_container_width=True):
    _set_demo(True)

# Show payload for transparency
with st.expander("Request payload (read-only)"):
    st.code(json.dumps(build_payload(), indent=2), language="json")


# ----------------- render helpers -----------------
def render_evaluations(evals: List[Dict[str, Any]]) -> None:
    for ev in evals:
        req = ev.get("requirement", "")
        status = ev.get("status", "Unknown")
        evidence = ev.get("evidence", []) or []
        conf = ev.get("confidence", None)

        badge = {
            "Met": "✅ Met",
            "Partially met": "🟡 Partial",
            "Partial": "🟡 Partial",
            "Missing": "❌ Missing",
        }.get(status, status)

        conf_txt = f" · conf {conf:.2f}" if isinstance(conf, (int, float)) else ""
        st.markdown(f"- **{req}** — {badge}{conf_txt}")
        if evidence:
            if isinstance(evidence, (list, tuple)):
                for e in evidence:
                    st.code(str(e))
            else:
                st.code(str(evidence))

def render_counterfactuals(suggestions: Union[List[Any], Dict[str, Any]]) -> None:
    if isinstance(suggestions, dict):
        for section, items in suggestions.items():
            st.markdown(f"#### {section}")
            if not items:
                st.caption("No suggestions.")
                continue
            for s in items:
                if isinstance(s, str):
                    st.markdown(f"- {s}")
                else:
                    rule = s.get("rule", "suggestion")
                    before = s.get("before", "")
                    after = s.get("after", "")
                    why = s.get("why", "")
                    st.markdown(f"- **{rule}**")
                    if before:
                        st.caption("Before"); st.code(before)
                    if after:
                        st.caption("After"); st.code(after)
                    if why:
                        st.caption("Why"); st.write(why)
    else:
        items = suggestions or []
        if not items:
            st.caption("No suggestions.")
        for s in items:
            if isinstance(s, str):
                st.markdown(f"- {s}")
            else:
                rule = s.get("rule", "suggestion")
                before = s.get("before", "")
                after = s.get("after", "")
                why = s.get("why", "")
                st.markdown(f"- **{rule}**")
                if before:
                    st.caption("Before"); st.code(before)
                if after:
                    st.caption("After"); st.code(after)
                if why:
                    st.caption("Why"); st.write(why)


# ----------------- actions -----------------
def has_inputs(p: Dict[str, Any]) -> bool:
    have_resume = bool(p.get("resume") or p.get("resume_path"))
    have_job    = bool(p.get("job") or p.get("job_path"))
    return have_resume and have_job

if score_clicked:
    payload = build_payload()
    if not has_inputs(payload):
        st.error("Please provide a resume (text or file) **and** a job description (text or file).")
    else:
        with st.spinner("Scoring…"):
            try:
                data = post_json("/score", payload)
                score = data.get("score", 0.0)
                conf = data.get("confidence", 0.0)
                st.success(f"Score: **{score:.2f}** · Confidence: **{conf:.2f}**")
                st.subheader("Evaluations")
                render_evaluations(data.get("evaluations", []))
            except Exception as e:
                st.error(f"Score request failed: {e}")

if counter_clicked:
    payload = build_payload()
    if not has_inputs(payload):
        st.error("Please provide a resume (text or file) **and** a job description (text or file).")
    else:
        with st.spinner("Generating counterfactuals…"):
            try:
                data = post_json("/counterfactual", payload)
                st.subheader("Counterfactual suggestions")
                render_counterfactuals(data.get("suggestions", []))
            except Exception as e:
                st.error(f"Counterfactual request failed: {e}")

if action_clicked:
    payload = build_payload()
    if not has_inputs(payload):
        st.error("Please provide a resume (text or file) **and** a job description (text or file).")
    else:
        with st.spinner("Recommending action…"):
            try:
                data = post_json("/action", payload)
                decision = data.get("action") or data.get("decision") or "n/a"
                st.subheader("Recommended action")
                st.warning(f"**{decision}**")
                rationale = data.get("rationale")
                details = data.get("details")
                if rationale:
                    st.caption("Why"); st.write(str(rationale))
                if details:
                    st.caption("Details")
                    st.write(details if isinstance(details, str) else json.dumps(details, indent=2))
            except Exception as e:
                st.error(f"Action request failed: {e}")
