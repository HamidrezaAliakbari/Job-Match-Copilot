# ui/streamlit_app.py
import os
import re
import json
from typing import Any, Dict, List, Optional, Union

import requests
import streamlit as st


# ----------------- helpers: safe secrets/env -----------------
def safe_secret(key: str, default=None):
    """
    Read from Streamlit secrets first (if present), else from env, else default.
    Works on Render and locally.
    """
    try:
        return st.secrets.get(key, os.environ.get(key, default))  # type: ignore[attr-defined]
    except Exception:
        return os.environ.get(key, default)


# ----------------- configuration -----------------
st.set_page_config(page_title="Job-Match Copilot — UI", layout="wide")
st.title("💼 Job-Match Copilot (Render UI)")

# API base: set as env var on Render UI service (recommended)
DEBUG = (safe_secret("DEBUG", "0") == "1")
API_BASE = safe_secret("API_BASE", None)  # e.g. https://job-match-copilot-api.onrender.com

# Optional Render Protected Web Service header (only if you turned that on)
API_PROTECT_HEADER = safe_secret("API_PROTECT_HEADER", "X-Render-Secret")
API_PROTECT_TOKEN = safe_secret("RENDER_API_SECRET", None)

# Allow overriding base in sidebar in DEBUG mode
if DEBUG:
    st.sidebar.caption("API base (debug)")
    api_base = st.sidebar.text_input(
        "Base URL",
        value=(API_BASE or "http://127.0.0.1:8000"),
    ).rstrip("/")
else:
    api_base = (API_BASE or "").rstrip("/")

if not api_base:
    st.error(
        "API_BASE is not configured. Set it as an Environment Variable on this UI service.\n\n"
        "Example value: https://job-match-copilot-api.onrender.com"
    )
    st.stop()

# ----------------- sidebar: health check -----------------
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
        placeholder="Paste the resume text here…",
        height=260,
    )
    resume_path = st.text_input(
        "…or a resume file path (local dev only)",
        placeholder="e.g., data/samples/resume_sample.md",
    )

with right:
    st.subheader("Job")
    job_text = st.text_area(
        "Paste job description (recommended on cloud)",
        placeholder="Paste the job description here…",
        height=260,
    )
    job_path = st.text_input(
        "…or a job file path (local dev only)",
        placeholder="e.g., data/samples/job_sample.md",
    )

st.markdown("---")

req_csv = st.text_input(
    "Explicit requirements (comma-separated — optional)",
    value="Python, FastAPI, AWS",
    help="If provided, they are sent as 'requirements'. Leave blank to let the backend infer.",
)
requirements = [r.strip() for r in req_csv.split(",") if r.strip()]


# ----------------- UI sectionizers (client-only; scoring code remains unchanged) -----------------
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

def _take_bullets(lines: List[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if _BULLET.match(ln):
            out.append(_BULLET.sub("", ln).strip())
        else:
            out.append(ln.strip())
    return out

def sectionize_resume_ui(text: str) -> Dict[str, Any]:
    lines = [_n(l) for l in (text or "").splitlines()]
    current = "summary"
    buckets = {
        "skills": [],
        "experience_bullets": [],
        "projects": [],
        "education": [],
        "courses": [],
    }
    summary_chunks: List[str] = []

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

    # return summary separately (we'll fold it into experience_bullets before sending)
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

def _which_job_header(line: str) -> Optional[str]:
    h = _HDR_END.sub("", (line or "").strip()).lower()
    for bucket, names in _JOB_SECTIONS.items():
        if h in names:
            return bucket
    return None

def sectionize_job_ui(text: str, explicit_requirements=None, explicit_preferred=None) -> Dict[str, Any]:
    """
    If explicit lists are provided, those win.
    Otherwise parse the JD into title / requirements (minimum) / preferred.
    Header lines are filtered out of the lists.
    """
    if explicit_requirements or explicit_preferred:
        return {
            "title": "",
            "requirements": list(dict.fromkeys(explicit_requirements or [])),
            "preferred": list(dict.fromkeys(explicit_preferred or [])),
        }

    lines = [_n(l) for l in (text or "").splitlines()]
    bucket: Optional[str] = None
    title = ""
    reqs: List[str] = []
    prefs: List[str] = []
    buf: List[str] = []

    def flush(into: List[str]):
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
            if _BULLET.match(raw):
                reqs.append(_BULLET.sub("", raw).strip())
            else:
                buf.append(raw)
            continue

        if bucket == "preferred":
            if _BULLET.match(raw):
                prefs.append(_BULLET.sub("", raw).strip())
            else:
                buf.append(raw)
            continue

        # Ignore "about" for scoring

    if bucket == "minimum":
        flush(reqs)
    if bucket == "preferred":
        flush(prefs)

    # strip any surviving header-ish lines
    header_like = {h for names in _JOB_SECTIONS.values() for h in names}
    def _not_header(s: str) -> bool:
        return _HDR_END.sub("", s).lower() not in header_like

    reqs = [r for r in reqs if _not_header(r)]
    prefs = [p for p in prefs if _not_header(p)]

    # de-dupe keep order
    reqs = list(dict.fromkeys(reqs))
    prefs = list(dict.fromkeys(prefs))

    return {"title": title, "requirements": reqs, "preferred": prefs}


# ----------------- payload builders -----------------
ALLOWED_RESUME_KEYS = {"skills", "experience_bullets", "projects", "education", "courses"}

def sanitize_resume_for_api(res: Dict[str, Any]) -> Dict[str, Any]:
    """
    Your API model likely has Pydantic with extra=forbid and expects ONLY:
      skills, experience_bullets, projects, education, courses

    - If 'summary' exists, prepend it into experience_bullets.
    - Drop any unknown keys (like 'summary').
    - Drop empty strings and trim whitespace.
    """
    out: Dict[str, List[str]] = {k: [] for k in ALLOWED_RESUME_KEYS}

    # fold summary into experience_bullets
    summary = (res.get("summary") or "").strip()
    if summary:
        out["experience_bullets"].append(summary)

    def _clean_list(vals: List[str]) -> List[str]:
        cleaned: List[str] = []
        for v in vals or []:
            t = (v or "").strip()
            if t:
                cleaned.append(t)
        return cleaned

    for k in ALLOWED_RESUME_KEYS:
        out[k].extend(_clean_list(res.get(k) or []))

    # de-dupe each list but keep order
    for k in out:
        seen, uniq = set(), []
        for item in out[k]:
            key = item.lower()
            if key not in seen:
                seen.add(key); uniq.append(item)
        out[k] = uniq

    return out

def build_payload() -> Dict[str, Any]:
    """
    Build the JSON body expected by the API:
      {
        "resume": {skills, experience_bullets, projects, education, courses} OR "resume_path"
        "job": {title, requirements, preferred} OR "job_path"
        "requirements": [...],  # optional
      }
    """
    payload: Dict[str, Any] = {}

    if requirements:
        payload["requirements"] = [r for r in requirements if r.strip()]

    # ---- RESUME ----
    if resume_text.strip():
        # sectionize first (with summary), then sanitize for strict API schema
        res_ui = sectionize_resume_ui(resume_text)
        payload["resume"] = sanitize_resume_for_api(res_ui)
    elif resume_path.strip():
        payload["resume_path"] = resume_path.strip()

    # ---- JOB ----
    if job_text.strip():
        job_obj = sectionize_job_ui(
            job_text,
            explicit_requirements=None,   # set to `requirements` if you want sidebar to override
            explicit_preferred=None
        )
        # clean empties
        job_obj["requirements"] = [r for r in job_obj.get("requirements", []) if r.strip()]
        job_obj["preferred"] = [p for p in job_obj.get("preferred", []) if p.strip()]
        # drop empty title if blank
        if not job_obj.get("title", "").strip():
            job_obj["title"] = "Job"
        payload["job"] = job_obj
    elif job_path.strip():
        payload["job_path"] = job_path.strip()

    # Drop empty/None/{} to avoid confusing the API
    clean: Dict[str, Any] = {}
    for k, v in payload.items():
        if v in (None, "", [], {}):
            continue
        clean[k] = v

    return clean


def has_inputs(p: Dict[str, Any]) -> bool:
    """
    Require a resume (object or path) AND a job (object or path).
    """
    have_resume = bool(p.get("resume") or p.get("resume_path"))
    have_job = bool(p.get("job") or p.get("job_path"))
    return have_resume and have_job


# ----------------- HTTP -----------------
def post_json(path: str, body: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    url = f"{api_base}{path}"
    r = requests.post(url, json=body, headers=_auth_headers(), timeout=timeout)
    # Surface detailed backend errors in the UI
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = json.dumps(r.json(), indent=2)
        except Exception:
            detail = r.text
        raise requests.HTTPError(f"{e}\n---- Backend response ----\n{detail}") from None
    return r.json()


# ----------------- buttons -----------------
b1, b2, b3 = st.columns([1, 1, 1])
score_clicked = b1.button("Ingest & Score", type="primary", use_container_width=True)
counter_clicked = b2.button("Counterfactuals", use_container_width=True)
action_clicked = b3.button("Action", use_container_width=True)

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
                st.error(f"Score request failed:\n{e}")

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
                st.error(f"Counterfactual request failed:\n{e}")

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
                st.error(f"Action request failed:\n{e}")
