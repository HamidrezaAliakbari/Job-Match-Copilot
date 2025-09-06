import streamlit as st
import requests

st.set_page_config(page_title="Job-Match Copilot", layout="wide")
st.title("💼 Job-Match Copilot (MVP)")

api_base = st.sidebar.text_input("API base", "http://127.0.0.1:8000")
st.sidebar.markdown("Tip: start Uvicorn from the project root so relative paths like `data/samples/...` work.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Resume")
    resume_text = st.text_area("Paste resume text (or leave blank if using file paths)")
    resume_path = st.text_input("…or resume file path (e.g., data/samples/resume_sample.md)")
with col2:
    st.subheader("Job")
    job_text = st.text_area("Paste job description (or leave blank if using file paths)")
    job_path = st.text_input("…or job file path (e.g., data/samples/job_sample.md)")

st.markdown("---")

if st.button("Ingest & Score", type="primary"):
    payload = {}
    if resume_text.strip():
        payload["resume"] = {
            "skills": [],
            "experience_bullets": [l for l in resume_text.splitlines() if l.strip()],
            "projects": [],
        }
    elif resume_path.strip():
        payload["resume_path"] = resume_path.strip()

    if job_text.strip():
        payload["job"] = {
            "title": "Job",
            "requirements": [l.strip("-• ").strip() for l in job_text.splitlines() if l.strip()],
            "preferred": [],
        }
    elif job_path.strip():
        payload["job_path"] = job_path.strip()

    if not payload:
        st.error("Provide either resume/job text or file paths.")
    else:
        try:
            s = requests.post(f"{api_base}/score", json=payload, timeout=60).json()
            st.success(f"Score: {s.get('score',0):.2f} | Confidence: {s.get('confidence',0):.2f}")
            st.subheader("Evaluations")
            for ev in s.get("evaluations", []):
                st.markdown(f"**{ev['requirement']}** — *{ev['status']}*")
                for snip in ev.get("evidence", []):
                    st.code(snip)

            st.subheader("Counterfactuals")
            cf = requests.post(f"{api_base}/counterfactual", json=payload, timeout=60).json()
            for sug in cf.get("suggestions", []):
                st.markdown(f"- **{sug.get('change_type','')}** → {sug.get('target_requirement','')}")
                if sug.get("before"):
                    st.caption("Before"); st.code(sug["before"])
                if sug.get("after"):
                    st.caption("After"); st.code(sug["after"])
                if sug.get("rationale"):
                    st.caption("Why"); st.write(sug["rationale"])

            st.subheader("Action")
            act = requests.post(f"{api_base}/action", json=payload, timeout=60).json()
            st.warning(f"Suggested action: **{act.get('decision','n/a')}**")
            st.json(act.get("details", {}))
        except Exception as e:
            st.error(f"Request failed: {e}")
