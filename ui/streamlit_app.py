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

# ----------------- inputs -----------------
left, right = st.columns(2)

with left:
    st.subheader("Resume")
    resume_text = st.text_area(
        "Paste resume text (recommended on cloud)",
        placeholder="Paste the resume text here…",
        height=220,
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
        height=220,
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


# ----------------- minimal parsing helpers (safe for demo) -----------------
_BULLET_RE = re.compile(r"^\s*([\-*•–]|(\d+\.)|(\d+\)))\s+")

def _extract_bullets(text: str, max_items: int = 20) -> List[str]:
    """
    Try to turn a block of text into a list of bullets using common bullet/number patterns.
    Fallback: take non-empty lines. Keep items shortish.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    items: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if _BULLET_RE.match(ln) or ";" in ln:
            # split on semicolons if user pasted "a; b; c"
            parts = [p.strip(" •*-–\t") for p in re.split(r"[;•]", ln) if p.strip()]
            for p in parts:
                if 2 <= len(p) <= 300:
                    items.append(p)
        else:
            # collect shortish lines as bullets too
            if 2 <= len(ln) <= 300:
                items.append(ln)
        if len(items) >= max_items:
            break
    if not items and text.strip():
        items = [text.strip()]
    return items

def _guess_skills_from_text(text: str, max_items: int = 15) -> List[str]:
    """
    Extremely light heuristic for demo purposes: pull comma/semicolon-separated short tokens
    from lines containing 'Skills' or at the top of the text.
    """
    skills: List[str] = []
    for ln in text.splitlines()[:10]:
        if "skill" in ln.lower() or "," in ln or ";" in ln:
            parts = re.split(r"[,\u2022;|/]+", ln)
            for p in parts:
                t = p.strip()
                if 1 < len(t) <= 32 and any(ch.isalpha() for ch in t):
                    # skip obviously long phrases
                    if " " in t and len(t.split()) > 4:
                        continue
                    skills.append(t)
    # dedupe preserve order
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

def _extract_requirements(text: str, max_items: int = 25) -> List[str]:
    """
    Extract lines that look like requirements from job text.
    Prefer bulleted/numbered lines; fallback to non-empty lines.
    """
    items = _extract_bullets(text, max_items=max_items)
    # keep reasonably sized items
    items = [it for it in items if 2 <= len(it) <= 300]
    if not items and text.strip():
        items = [text.strip()]
    return items[:max_items]


# ----------------- payload builders -----------------
def build_payload() -> Dict[str, Any]:
    """
    Build the JSON body expected by the API:
      {
        "resume": {skills, experience_bullets, projects, education, courses} OR "resume_path"
        "job": {title, requirements, preferred} OR "job_path"
        "requirements": [...], "preferred": [...]
      }
    """
    payload: Dict[str, Any] = {}
    if requirements:
        payload["requirements"] = requirements
    payload["preferred"] = None  # keep explicit for now

    # ---- RESUME ----
    if resume_text.strip():
        payload["resume"] = {
            "skills": _guess_skills_from_text(resume_text),
            "experience_bullets": _extract_bullets(resume_text),
            "projects": [],
            "education": [],
            "courses": [],
        }
    elif resume_path.strip():
        payload["resume_path"] = resume_path.strip()

    # ---- JOB ----
    if job_text.strip():
        payload["job"] = {
            "title": "Job",
            "requirements": _extract_requirements(job_text),
            "preferred": [],
        }
    elif job_path.strip():
        payload["job_path"] = job_path.strip()

    # Drop empty/None
    return {k: v for k, v in payload.items() if v not in (None, [], "")}


def has_inputs(p: Dict[str, Any]) -> bool:
    """
    New validation: require a resume (object or path) AND a job (object or path).
    This matches the API you have live.
    """
    have_resume = bool(p.get("resume") or p.get("resume_path"))
    have_job = bool(p.get("job") or p.get("job_path"))
    return have_resume and have_job


# ----------------- HTTP -----------------
def post_json(path: str, body: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    url = f"{api_base}{path}"
    r = requests.post(url, json=body, headers=_auth_headers(), timeout=timeout)
    r.raise_for_status()
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
