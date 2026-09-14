# Backend

FastAPI backend for the AI Learning Workspace (Phase 1: Book Intelligence).
Module layout and interface boundaries: `docs/ARCHITECTURE.md` §2–3.
Schema: `docs/DOMAIN_MODEL.md`.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env   # optional; all settings come from env (ALW_ prefix)
```

## Verification

```bash
ruff check . && mypy .
pytest                  # unit tests only, no services required
```

Integration tests (migrations + DB) need a local Postgres 16 with pgvector:

```bash
docker run -d --name alw-pg -e POSTGRES_PASSWORD=postgres -p 5433:5432 pgvector/pgvector:pg16
export TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5433/postgres"
export ALW_DATABASE_URL="$TEST_DATABASE_URL"   # used by alembic
pytest -m integration
docker stop alw-pg && docker rm alw-pg
```

The pgvector image ships the `vector` extension; the initial migration runs
`CREATE EXTENSION IF NOT EXISTS vector` and needs a role allowed to create
extensions (the default superuser works).

## Run (dev)

```bash
uvicorn app.main:app --reload
curl -i localhost:8000/health   # includes X-Correlation-ID
```

## Extractors

Two interchangeable PDF extractors behind the `TextExtractor` protocol:

- `pymupdf` (default): fast, text-layer extraction with page provenance.
- `mineru`: layout-aware parsing (reading order, headings, tables→HTML,
  formulas→LaTeX, header/footer removal). Requires a separate install because
  MinerU needs Python 3.10–3.13 while this project targets 3.12+:

```bash
uv venv .venv-mineru --python 3.13
uv pip install --python .venv-mineru/bin/python 'mineru[core]'   # ~2GB incl. models
```

Then switch via env (command must point at that venv's binary):

```bash
ALW_EXTRACTOR=mineru
ALW_MINERU_COMMAND=$PWD/.venv-mineru/bin/mineru
```

Re-ingest a book to re-parse it; page provenance and heading-derived TOC come
from MinerU's content list. Figures are detected (captions enter the text) but
image content itself is a future multimodal step.

## Config

pydantic-settings, prefix `ALW_`, `.env` supported (gitignored). Secrets
(`ALW_OPENAI_API_KEY` etc.) are provided at dev time only — never committed.
