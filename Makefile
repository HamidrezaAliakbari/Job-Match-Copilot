PYTHON=python
PIP=$(PYTHON) -m pip
VENV?=.venv

.PHONY: setup serve test clean

# Create a virtual environment and install dependencies
setup:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && $(PIP) install -r requirements.txt

# Run the FastAPI server locally
serve:
	. $(VENV)/bin/activate && uvicorn app.api:app --reload --port 8000

# Run the smoke tests
test:
	. $(VENV)/bin/activate && pytest -q

# Remove the virtual environment (use with care)
clean:
	rm -rf $(VENV)

Courses:
Enhancing the Recruitment of Marginalized Communities in Clinical Trials – Vanderbilt University
