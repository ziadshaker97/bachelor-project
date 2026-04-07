# Employee Onboarding Intelligence MVP

This repository contains a model-first MVP for an employee onboarding dashboard with:

- A Python FastAPI backend
- A React frontend
- A content-based recommendation engine seeded from OULAD-inspired data
- A RAG chatbot grounded in mock firm onboarding documents and Doc2Dial-style document QA behavior

## Workspace layout

- `backend/` FastAPI app, SQLite storage, services, and tests
- `frontend/` React dashboard
- `backend/data/raw/` downloaded source datasets for OULAD and Doc2Dial
- `backend/data/processed/` runtime artifacts derived from the real datasets
- `backend/data/seed/` mock firm documents and runtime module catalog

## Backend quick start

Python is required locally to run the backend.

Suggested local steps:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python scripts/bootstrap_datasets.py
python -m uvicorn app.main:app --reload
pytest
```

## Real dataset bootstrap

The recommendation and chat guidance layers now use processed artifacts derived from the real OULAD and Doc2Dial datasets.

Bootstrap commands:

```bash
cd backend
python scripts/prepare_oulad.py
python scripts/prepare_doc2dial.py
```

Or run both with:

```bash
cd backend
python scripts/bootstrap_datasets.py
```

This downloads the official archives locally, extracts them into `backend/data/raw/`, and writes app-ready artifacts into `backend/data/processed/`.

### Free local LLM runtime

The backend defaults to an extractive grounded fallback so the app can run even when no model server is available.
To use a free local open-source model through Ollama:

```bash
cd backend
copy .env.example .env
```

Then install Ollama, pull a lightweight free model, and start the Ollama server:

```bash
ollama pull llama3.2:3b
ollama serve
```

With the default `.env`, the backend will call Ollama at `http://127.0.0.1:11434` using `llama3.2:3b`.
If Ollama is unavailable, the app now falls back to the grounded extractive mode instead of failing.

## Frontend quick start

```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://127.0.0.1:8001` by default.
