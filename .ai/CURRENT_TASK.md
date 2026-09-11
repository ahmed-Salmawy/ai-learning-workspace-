# Current Task

Goal: Begin Phase 1 (Book Intelligence) implementation at M0 per docs/PHASE1_PLAN.md.

Why: Architecture bootstrap (README §62) is complete; §62 authorizes implementation start.

Status: Not started (design-only repository).

Files:

- docs/PHASE1_PLAN.md        (authoritative plan; M0–M5)
- docs/ARCHITECTURE.md       (module layout to scaffold)
- docs/DOMAIN_MODEL.md       (migrations to write in M0)
- docs/adr/*                 (constraints to honor while building)

Completed (bootstrap):

- All §62 artifacts: architecture docs, ADRs 001–003, capsule, schema design, Phase 1 plan, Roadmint analysis

Remaining (Phase 1):

- M0: FastAPI scaffold, Alembic + initial migrations, interface protocols + fakes, lint/type/test wiring
- M1: ingestion pipeline (upload → parse → TOC/chapters → chunking, idempotent)
- M2: embeddings + concept extraction (validated schemas)
- M3: Ask the Book (pgvector retrieval, citations, isolation)
- M4: minimal Next.js UI (upload + ask with citations)
- M5: hardening + end-to-end DoD verification (2 books, zero cross-book leakage)

Acceptance Criteria (README §39 Phase 1 DoD):

- Upload multiple books; ask questions against each independently with citations
- No cross-book leakage anywhere (retrieval filters workspace_id + book_id)
- Re-ingestion creates no duplicates; failed stages resume

Known Issues:

- LLM/embedding provider needs env credentials at dev time (OPENAI_BASE_URL/KEY style); not committed
- Local Postgres+pgvector via Docker required for integration tests

Next Action:

Implement M0 step 1: FastAPI scaffold (backend/app/* per docs/ARCHITECTURE.md §3) with config, logging, correlation-ID middleware, and a health endpoint; then Alembic init + first migrations.
