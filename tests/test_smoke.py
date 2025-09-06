import json
from fastapi.testclient import TestClient

from app.api import app


def test_score_endpoint(tmp_path):
    client = TestClient(app)
    # copy sample files into a temporary directory for isolation
    resume_src = "sample_data/resume_sample.txt"
    job_src = "sample_data/job_sample_ds.txt"
    resume_dst = tmp_path / "resume.txt"
    job_dst = tmp_path / "job.txt"
    resume_dst.write_text(open(resume_src).read())
    job_dst.write_text(open(job_src).read())
    payload = {
        "resume_path": str(resume_dst),
        "job_path": str(job_dst),
        "requirements": [
            "Proficiency in Python, scikit-learn and pandas",
            "Experience deploying machine learning models"
        ],
        "preferred": ["Knowledge of SQL"]
    }
    response = client.post("/score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "evidence" in data