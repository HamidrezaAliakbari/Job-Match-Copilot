import os
import json
import requests
import streamlit as st

st.set_page_config(page_title="Job-Match Copilot — beta-02", layout="wide")
st.title("💼 Job-Match Copilot (beta-02)")

API_BASE_ENV = os.environ.get("API_BASE", "").rstrip("/")
api_base = st.sidebar.text_input("API base", value=API_BASE_ENV or "http://127.0.0.1:8000").rstrip("/")

with st.sidebar:
    if st.button("Check API health"):
        try:
            r = requests.get(f"{api_base}/healthz", timeout=10)
            st.success(r.json())
        except Exception as e:
            st.error(f"Health failed: {e}")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Resume")
    resume_text = st.text_area("Paste resume text (recommended for cloud)")
    resume_path = st.text_input("…or resume file path (for local tests)")
with col2:
    st.subheader("Job")
    job_text = st.text_area("Paste job description (recommended for cloud)")
    job_path = st.text_input("…or job file path (for local tests)")

st.markdown("---")
req_csv = st.text_input("Explicit requirements (comma-separated)", value="Python, scikit-learn")
requirements = [r.strip() for r in req_csv.split(",") if r.strip()]

btn1, btn2, btn3 = st.columns([1,1,1])
score_clicked = btn1.button("Ingest & Score", type="primary", use_container_width=True)
counter_clicked = btn2.button("Counterfactuals", use_container_width=True)
action_clicked = btn3.button("Action", use_container_width=True)

def build_payload():
    payload = {"requirements": requirements, "preferred": None}
    if resume_text.strip():
        payload["resume_text"] = resume_text.strip()
    elif resume_path.strip():
        payload["resume_path"] = resume_path.strip()
    if job_text.strip():
        payload["job_text"] = job_text.strip()
    elif job_path.strip():
        payload["job_path"] = job_path.strip()
    return payload

def post(path: str, body: dict, timeout=60):
    url = f"{api_base}{path}"
    r = requests.post(url, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()

with st.expander("Request payload (read-only)"):
    st.code(json.dumps(build_payload(), indent=2))

if score_clicked:
    payload = build_payload()
    if not any(payload.get(k) for k in ("resume_text","resume_path","job_text","job_path")):
        st.error("Provide at least resume text/path or job text/path.")
    else:
        try:
            data = post("/score", payload)
            st.success(f"Score: {data.get('score', 0):.2f} | Confidence: {data.get('confidence', 0):.2f}")
            st.subheader("Evaluations")
            for ev in data.get("evaluations", []):
                req = ev.get("requirement", "")
                met = ev.get("met", False)
                evidence = ev.get("evidence") or ""
                conf = ev.get("confidence")
                conf_str = "" if conf is None else f" — conf {conf:.2f}"
                st.markdown(f"- **{req}** → {'✅ Met' if met else '❌ Not met'}{conf_str}")
                if evidence:
                    st.code(str(evidence))
        except Exception as e:
            st.error(f"Request failed: {e}")

if counter_clicked:
    payload = build_payload()
    if not any(payload.get(k) for k in ("resume_text","resume_path","job_text","job_path")):
        st.error("Provide at least resume text/path or job text/path.")
    else:
        try:
            data = post("/counterfactual", payload)
            st.subheader("Counterfactual suggestions")
            suggs = data.get("suggestions", [])
            if not suggs:
                st.info("No suggestions returned.")
            else:
                for s in suggs:
                    st.markdown(f"- {s if isinstance(s, str) else str(s)}")
        except Exception as e:
            st.error(f"Request failed: {e}")

if action_clicked:
    payload = build_payload()
    if not any(payload.get(k) for k in ("resume_text","resume_path","job_text","job_path")):
        st.error("Provide at least resume text/path or job text/path.")
    else:
        try:
            data = post("/action", payload)
            st.subheader("Recommended action")
            st.warning(f"**{data.get('action','n/a')}**")
            if data.get("rationale"):
                st.caption("Why")
                st.write(str(data["rationale"]))
        except Exception as e:
            st.error(f"Request failed: {e}")
