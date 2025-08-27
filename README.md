# Job‑Match Copilot

This repository contains a self‑contained starter implementation of a “Job‑Match Copilot.”  The goal of the project is to help recruiters and candidates understand how well a resume matches a job description, with transparent evidence and actionable next steps.  It demonstrates a small end‑to‑end stack using Python and FastAPI.

## What it does

* Parses a resume and a job description into simple JSON structures.
* Computes a rough match score between the resume and the job requirements.
* Extracts evidence sentences from the resume to justify each requirement match.
* Suggests minimal, non‑fabricated edits (“counterfactuals”) to improve the match.
* Recommends an action (interview, request more information, or suggest a learning path) based on the score.

This starter does **not** call any large language models.  Instead, it uses TF–IDF similarity and simple heuristics to keep the demo portable and free of external dependencies.  You can later swap the logic for more advanced retrieval, classification or fine‑tuned LLMs.

## Installation

1. Clone the repo and switch into the directory:

   ```bash
   git clone <your‑repo‑url> job_match_copilot
   cd job_match_copilot
   ```

2. Create a virtual environment and install requirements (Python 3.9+).  The requirements are kept minimal so that they install quickly and do not require network access.  If you don’t need a virtualenv, you can skip the first two lines.

   ```bash
   python -m venv venv
   source venv/bin/activate      # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the API locally:

   ```bash
   uvicorn app.api:app --reload --port 8000
   ```

4. In another terminal, you can call the endpoints using `curl` or any HTTP client.  For example, to score the included sample files:

   ```bash
   curl -X POST http://localhost:8000/score \
        -H "Content-Type: application/json" \
        -d @sample_data/sample_request.json
   ```

The response includes the match score, confidence and per‑requirement evidence.

## Repository structure

The project is intentionally modular.  The top‑level folders are:

| Path                 | Purpose                                                                      |
|----------------------|-------------------------------------------------------------------------------|
| `app/`               | FastAPI application and Pydantic schemas.                                     |
| `core/`              | Core logic for parsing, retrieval, scoring, counterfactuals and policy.        |
| `models/`            | Placeholder for fine‑tuned models (not used in this demo).                    |
| `data/`              | Ontology or taxonomy files (currently empty).                                 |
| `sample_data/`       | Example resume and job description, plus a JSON request for testing.          |
| `tests/`             | Smoke tests to verify that the API runs and returns sane values.              |
| `infra/`             | Space for Dockerfiles or deployment scripts (not implemented here).           |
| `Makefile`           | A few helper targets (install, serve, test).                                  |

## Next steps

This starter is deliberately simple so that you can iterate quickly.  To extend it into a fully‑fledged job‑matching copilot, consider the following enhancements:

* Replace the simple TF–IDF retrieval with better embeddings (e.g. `bge-large-en`) and a vector database such as Qdrant.
* Write LoRA adapters for requirement classification and evidence extraction, then integrate them in `core/reason_llm.py`.
* Improve the skill ontology in `data/` and use it to normalise terms across resumes and job descriptions.
* Add a front‑end: Streamlit or Next.js can call the FastAPI endpoints and display evidence cards and counterfactual patches.
* Containerise the app with a Dockerfile and deploy it on a cloud platform (AWS ECS, for instance).

Feel free to fork and build upon this starter.  Pull requests are welcome!