# Phase 1 Implementation Plan — Book Intelligence

Last Verified: 8319ed1 (2026-09-11)

Scope = README §39 Phase 1: upload, parsing, chunking, embeddings, chapter detection, concept extraction, Ask Book, citations, book isolation. **Out of scope:** roadmaps (Phase 2), sessions/notes (Phase 3), assessments (Phase 4), recall (Phase 5), cross-book (Phase 6).

**Definition of Done (README §39):** I can upload multiple books and ask questions against each independently, with citations, and no cross-book leakage.

## Milestones (build order; each ends in a verified, committable state)

### M0 — Skeleton & contracts (no AI calls)
1. `backend/` FastAPI scaffold + pydantic-settings config + structured logging + correlation-ID middleware.
2. Alembic init; migrations for schema subset: users, workspaces, books, book_sources, chapters, content_chunks, concepts (+ embedding column), learning_events.
3. Interface protocols: `LLMProvider`, `EmbeddingProvider`, `RetrievalEngine`, `RoadmapEngine` (extractConcepts/buildDependencies only for Phase 1), `ObjectStorage` — with fakes for tests.
4. CI-able checks wired: `ruff`, `mypy`, `pytest` (see Verification).

### M1 — Ingestion pipeline (deterministic core)
1. `POST /workspaces/{ws}/books` upload → ObjectStorage (local), `book_sources` row, `books.status=UPLOADED`.
2. Worker job chain (idempotent, restartable, per-stage status on `books`):
   extract text (PyMuPDF for PDF; plain/markdown passthrough) → metadata + TOC detection → chapters → semantic chunking (RAG §4 rules) → rows in `content_chunks` with `content_hash` dedup.
3. Re-upload same file ⇒ no duplicates (hash check + unique constraints); failed stage resumes.
4. Unit tests: chunker boundaries, TOC parsing fixtures, dedup idempotency, resume-from-failure.

### M2 — Embeddings + concepts
1. Embedding job: content-addressed (skip on hash+model match), writes `embedding` + `embedding_model`.
2. `LLMProvider` adapter (OpenAI-compatible via env config; no keys in repo).
3. Concept extraction via `RoadmapEngine.extractConcepts` → schema-validated JSON → `concepts` with `normalized_name` dedup; `buildDependencies` → `concept_relationships` (stored now, consumed in Phase 2).
4. Tests: schema-validation retry/failure path, dedup, isolation (concepts never cross books).

### M3 — Ask the Book (RAG live)
1. `PgVectorRetrievalEngine` + HNSW index; hard `workspace_id + book_id` filter.
2. `POST /books/{id}/ask` orchestration per docs/RAG_ARCHITECTURE.md: retrieve → generate → validate response schema → citation intersection → persist `conversations/messages`.
3. Insufficient-evidence path returns the explicit §21 message; general-knowledge note is a separate labeled field.
4. Tests: citation fidelity (no invented pages), isolation (Book A question never returns Book B passages), insufficient-evidence contract.

### M4 — Minimal UI (thin slice)
1. Next.js scaffold: upload page, book list, book workspace with chat ("Ask Book") showing citations.
2. No roadmap/session UI yet — Phase 1 surface only.

### M5 — Hardening & DoD verification
1. Observability: ingestion stage metrics, LLM latency/token counters (README §36 subset).
2. End-to-end test: upload 2 books (different domains), ask each independently, assert zero cross-book citation leakage.
3. Update `.ai/` capsule; ADR for any deviation discovered during build.

## Verification Commands (finalized in M0; see backend/README.md)

```bash
cd backend                       # venv via uv (see backend/README.md)
ruff check . && mypy .           # lint + types
pytest                           # unit tests, no services required
pytest -m integration            # migrations + ingestion + ask + DoD (needs TEST_DATABASE_URL,
                                 # local Postgres 16 + pgvector: docker run -e POSTGRES_PASSWORD=…
                                 # -p 5433:5432 pgvector/pgvector:pg16; export TEST_DATABASE_URL
                                 # and ALW_DATABASE_URL)
```

Frontend (Phase 1 M4): `cd frontend && npm run typecheck && npm run build`.

Integration tests require a local Postgres 16 with pgvector (`docker run -e POSTGRES_PASSWORD=… pgvector/pgvector:pg16`) — document in `backend/README.md` at M0.

## Explicit Environment Prerequisites (decisions recorded here, no secrets committed)

- Python 3.12+, Node 20+.
- `OPENAI_BASE_URL` / `OPENAI_API_KEY` style env vars for LLM+embeddings — user provides at dev time.
- Local Postgres + pgvector via Docker; object storage = local disk (abstracted).

## Risks

| Risk | Mitigation |
|---|---|
| TOC/chapter detection quality varies by PDF | TOC parser + heuristic fallback both log confidence; manual chapter fix API deferred to backlog |
| Embedding model choice affects everything downstream | Decide at M2 start; `embedding_model` column + re-embed job designed in from day 1 |
| LLM structured-output flakiness | Validated schema + bounded retry-with-error-feedback + hard failure surfaced in metrics |
| Scope creep into Phase 2 | Roadmap work stays behind `RoadmapEngine` stubs; no roadmap tables/UI in Phase 1 |
