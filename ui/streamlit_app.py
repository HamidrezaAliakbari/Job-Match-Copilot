# ui/streamlit_app.py
import os
import json
from typing import Any, Dict, List, Optional, Union

import requests
import streamlit as st

def safe_secret(key: str, default=None):
    try:
        return st.secrets.get(key, os.environ.get(key, default))  # type: ignore[attr-defined]
    except Exception:
        return os.environ.get(key, default)

API_PROTECT_HEADER = "X-Render-Secret"   # Render’s default header name
API_SECRET = safe_secret("RENDER_API_SECRET", None)


# ----------------- helpers: safe secrets -----------------


# ----------------- page config -----------------
st.set_page_config(page_title="Job-Match Copilot — UI", layout="wide")
st.title("💼 Job-Match Copilot (Render UI)")

# ----------------- production-safe API base -----------------
# Use env var API_BASE on Render. DEBUG=1 enables sidebar override for local dev.
DEBUG = (safe_secret("DEBUG", "0") == "1")
API_BASE = safe_secret("API_BASE", None)

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
        "API_BASE is not configured. Set it as an Environment Variable on this UI service.\n"
        "Example: https://job-match-copilot.onrender.com"
    )
    st.stop()

# Sidebar health check
if st.sidebar.button("Check API health"):
    try:
        r = requests.get(f"{api_base}/healthz", timeout=10)
        r.raise_for_status()
        st.sidebar.success(r.json())
    except Exception as e:
        st.sidebar.error(f"Health failed: {e}")

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
    help="If provided, they are sent as 'requirements'. Leave blank to let the backend extract them.",
)
requirements = [r.strip() for r in req_csv.split(",") if r.strip()]

# ----------------- payload -----------------
def post_json(path: str, body: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    url = f"{api_base}{path}"
    headers = {"Content-Type": "application/json"}
    if API_SECRET:  # only add when protection is enabled
        headers[API_PROTECT_HEADER] = API_SECRET
    r = requests.post(url, json=body, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()
    
def build_payload():
    """
    Build the JSON body expected by the API:
      {
        "resume": {skills, experience_bullets, projects, education, courses} OR "resume_path"
        "job": {title, requirements, preferred} OR "job_path"
        "requirements": [...], "preferred": [...]
      }
    """
    payload = {"requirements": requirements or None, "preferred": None}

    # ---- RESUME ----
    if resume_text.strip():
        # Super-simple parser: treat the pasted resume as one experience bullet.
        # (You can improve later by splitting lines and extracting skills)
        resume_obj = {
            "skills": [],  # keep empty unless you parse skills from text
            "experience_bullets": [resume_text.strip()],
            "projects": [],
            "education": [],
            "courses": [],
        }
        payload["resume"] = resume_obj
    elif resume_path.strip():
        payload["resume_path"] = resume_path.strip()

    # ---- JOB ----
    if job_text.strip():
        # Minimal mapping: use pasted JD as a single requirement line
        job_obj = {
            "title": "Job",
            "requirements": [job_text.strip()],
            "preferred": [],
        }
        payload["job"] = job_obj
    elif job_path.strip():
        payload["job_path"] = job_path.strip()

    # Drop Nones
    return {k: v for k, v in payload.items() if v is not None}



# ----------------- HTTP -----------------
def post_json(path: str, body: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    url = f"{api_base}{path}"
    r = requests.post(url, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()

# ----------------- buttons -----------------
b1, b2, b3 = st.columns([1, 1, 1])
score_clicked = b1.button("Ingest & Score", type="primary", use_container_width=True)
counter_clicked = b2.button("Counterfactuals", use_container_width=True)
action_clicked = b3.button("Action", use_container_width=True)

def ensure_inputs(p: Dict[str, Any]) -> Optional[str]:
    if not any(p.get(k) for k in ("resume_text", "resume_path")):
        return "Provide resume text (cloud) or a local file path."
    if not any(p.get(k) for k in ("job_text", "job_path")):
        return "Provide job description text (cloud) or a local file path."
    return None

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
    err = ensure_inputs(payload)
    if err:
        st.error(err)
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
    err = ensure_inputs(payload)
    if err:
        st.error(err)
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
    err = ensure_inputs(payload)
    if err:
        st.error(err)
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
                
