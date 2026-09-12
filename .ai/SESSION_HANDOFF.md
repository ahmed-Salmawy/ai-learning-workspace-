# Session Handoff

Date: 2026-09-11
Last Verified: working tree, uncommitted on top of 18dbe67

## Worked On

1. AGENTS.md audit (all claims verified; fixed stale skills note; added exact verify commands).
2. Manual ingestion of first Phase 1 test book per `skills/ingest-book` → `data/books/grokking-ai-applications/`.
3. **M0 implemented and verified end-to-end** (backend skeleton & contracts per docs/PHASE1_PLAN.md).

## M0 Result (the part that matters)

- `backend/` follows docs/ARCHITECTURE.md §3 layout. App factory in `app/main.py`; config via pydantic-settings, env prefix `ALW_` (see `backend/.env.example`); JSON logs + correlation-ID contextvar; middleware echoes/validates/generates `X-Correlation-ID`.
- Alembic migration `0001` = M0 schema subset from docs/DOMAIN_MODEL.md: users, workspaces, books, book_sources, chapters, content_chunks, concepts (Vector(1536) + HNSW cosine), learning_events (BRIN). Non-native enums (varchar + check) chosen for migration friendliness.
- Protocols + in-memory fakes for all five Phase-1 interfaces; retrieval fake structurally enforces `workspace_id + book_id` (ADR-002 encoded in the fake's signature/behavior).
- Verification is real, not aspirational: `ruff check . && mypy .` clean (35 files); `pytest` 15 unit tests pass; `pytest -m integration` ran the migration upgrade/downgrade round-trip against `pgvector/pgvector:pg16` in Docker (port 5433, per backend/README.md); uvicorn boot + `/health` verified over real HTTP.

## Environment Gotchas (would bite a fresh agent)

- **pip is unbootable on this host** (macOS 26.2 + Homebrew Python 3.14.6): `platform.mac_ver()` returns `('', ('', '', ''), '')`, crashing pip's vendored truststore; Homebrew's framework `sitecustomize.py` also shadows any venv copy. **Use `uv`** (installed via brew): `uv venv .venv --python 3.14` + `uv pip install -e '.[dev]' --python .venv/bin/python`. All commands in `backend/README.md` assume the `.venv`.
- One-shot `export A=x B="$A"` in zsh expands `$A` before assignment — set `ALW_DATABASE_URL` in a separate command (this silently produced an empty DB URL once).
- Testcontainers-free integration testing: start the pgvector container manually, export `TEST_DATABASE_URL` + `ALW_DATABASE_URL`, run `pytest -m integration` (test upgrades AND downgrades; leaves DB at base).

## Files Changed (this session)

- AGENTS.md; .gitignore (books/, data/, var/, *.egg-info/)
- `backend/**` — new M0 scaffold (app/, alembic/, tests/, pyproject.toml, README.md, .env.example; `.venv` + egg-info gitignored)
- `.ai/*` capsule updated (CURRENT_TASK, PROJECT_STATE, SESSION_HANDOFF)

## Tests

- Unit: 15 passed (health, correlation middleware, config, protocols/fakes incl. isolation, top_k).
- Integration: 1 passed against live pg16+pgvector (migration round-trip), skipped without TEST_DATABASE_URL.

## M1 Result (added 2026-09-11)

- M0 + M1 both COMPLETE. M1 = upload API, page-aware PyMuPDF extraction (embedded-TOC + heuristic fallback per RAG §4), chapters, chunking with per-chunk page ranges + content_hash dedup, idempotent/resumable stage pipeline (books.status + books.error.stage). The MarkItDown page-provenance concern is resolved: the pipeline extracts via PyMuPDF with page numbers, NOT MarkItDown output.
- Isolation is enforced in repositories (every query filters workspace_id [+book_id], ADR-002) and storage keys follow `workspaces/{ws}/books/{id}/…`.
- Verified: ruff+mypy clean (53 files), 31 unit tests, 4 integration tests on real pgvector/pgvector:pg16 (dedup round-trip, cross-workspace isolation, migration upgrade/downgrade, resume-from-failure).
- Gotchas recorded: FastAPI dependency teardown runs AFTER background tasks → commit explicitly in the endpoint before scheduling a job; endpoints must validate workspace existence (FK protects, API 404s); migration/ORM column-name drift (metadata vs source_metadata) is the kind of thing integration tests exist to catch.

## M2 Result (added 2026-09-11)

- M0–M2 COMPLETE. Embedding stage is content-addressed (skips chunks already embedded with current model; re-embeds on model change — ties into DOMAIN_MODEL §3.4). Concept extraction is schema-validated JSON with bounded retry-with-error-feedback (ADR-001 invariant), then hard failure into books.error.
- Stage routing is capability-based: no providers configured ⇒ pipeline stops at CHUNKED (M1 semantics); with providers ⇒ EMBEDDED → READY. Engine returns display names; pipeline normalizes before repo lookup (normalized_name is the join key).
- Adapter contract detail: LLM JSON uses camelCase (fromConcept/toConcept) per RAG §2 — Pydantic aliases required, first integration run caught it.
- Test-infrastructure lesson: never manage SQLAlchemy test sessions manually — an assert before session.close() leaves an open transaction that blocks the module teardown's `downgrade` on table locks (symptom: pytest hangs after the last test). Use `with factory() as session:` everywhere.

## M3 Result (added 2026-09-11)

- M0–M3 COMPLETE. Ask pipeline enforces the two most dangerous RAG invariants structurally: (1) retrieval hard-filters `workspace_id + book_id` in SQL (ADR-002 — no unscoped vector search path exists); (2) citations are the INTERSECTION of model-claimed chunkIds with actually-retrieved chunks, and citation provenance (chapter/pages/section) comes from the retrieved rows, never from model text (RAG §3.2). Empty intersection or insufficientEvidence ⇒ exact §21 message ("I could not find enough material in this book to answer confidently.").
- Knowledge-layer separation persisted end-to-end: USER/LEARNER question, ASSISTANT/BOOK grounded answer with citations jsonb, optional ASSISTANT/SYSTEM general-knowledge note as a separate message (README §6, §24).
- Retry logic extracted to `app/llm/structured.py::structured_call` and shared by LLMRoadmapEngine + AskService (identical attempt/backoff semantics; engine tests unchanged).
- UUID canonicalization matters at the LLM boundary: models may return dash-less or non-canonical UUIDs; `intersect_citations` canonicalizes before matching (else valid citations silently drop).

## M4 Result (added 2026-09-11)

- `frontend/` is a minimal Next.js 15 App Router + TypeScript (strict) app: `/` lists books with status pills (polls while ingestion is in flight; shows FAILED stage/message), upload form; `/books/[bookId]` is the Ask workspace — citation chips (Ch./pp./section from server provenance), a distinct "Not answerable from this book" state, and general-knowledge notes rendered as a separate labeled block (README §21 knowledge-layer separation visible in UI).
- Backend gained CORSMiddleware (`ALW_CORS_ORIGINS`, default `http://localhost:3000`) and `backend/scripts/bootstrap_workspace.py` which creates the fixed default workspace `00000000-0000-0000-0000-000000000001` (frontend default).
- Verified: `tsc --noEmit` clean; `next build` clean; live smoke with dockerized pg16 + uvicorn + `next start`: HTML served, CORS header present for the UI origin, upload → background ingest → list all working through the exact API calls the UI makes. Without LLM env keys books settle at CHUNKED (capability routing — intended).
- Dev-machine gotcha: port 3000 is taken by another app here; use `npx next start -p 3100`.

## M5 Result (added 2026-09-11) — PHASE 1 COMPLETE

- Metrics: `app/core/metrics.py` (counters/histograms/timer, thread-safe, reset for tests) exposed at `GET /metrics`. Instrumentation: ingestion stages via decorator (`ingestion_stage_seconds`/`ingestion_stage_total{stage,status}`), `ingestion_chunks_inserted_total`, `embedding_seconds`, adapter `llm_latency_seconds`/`llm_calls_total`/`llm_tokens_total{kind,direction}`, `retrieval_latency_seconds`. Correlation IDs ride the logging context (README §36), not metric labels.
- DoD run (README §39): `tests/test_dod_e2e.py` — 2 different-domain books (Java concurrency / Italian cooking) ingested to READY, each asked independently with scripted contract-conformant LLMs; ZERO cross-book leakage asserted three ways: retrieval sets are disjoint and book-pure, every AskResult citation resolves to the asked book's chunks, every persisted ASSISTANT/BOOK message's citations match its conversation's book. Metrics snapshot asserted (each stage ok×2). LIMITATION: fake embeddings + scripted LLM (no ALW_OPENAI_* keys on this machine) — a live-LLM confirmation run remains optional.
- Deviations → `docs/adr/004-phase1-build-deviations.md` (indexed in DECISIONS.md): normalized-name-only concept dedup (sim-dedup → Phase 2), capability-based status routing, PyMuPDF over MarkItDown, closed tutor_mode enum, JSON metrics format. PHASE1_PLAN.md verification section now reflects real commands.
- Instrumentation bug caught by the DoD test itself: decorator stage names were all "run" (bad `split('_')[1]`) — the metrics assertions failed loudly, proving the metrics are actually checked.

## Phase 1 Final State

- backend/: 57 tests (15 integration on real pg16+pgvector), ruff + mypy clean (76 files); migrations 0001–0003; full ingestion → embeddings → concepts → ask pipeline; isolation enforced at repository + SQL level
- frontend/: Next.js 15 build clean, upload/list/ask with citations; CORS + bootstrap script
- Uncommitted working tree contains all of M0–M5 — commit is the obvious next action but requires explicit user request per repo convention.

## Live-LLM DoD Run (added 2026-09-11)

- `scripts/dod_live.py`: 2 different-domain books → READY → 4 live asks via real GLM (`glm-4.5-flash`, z.ai). Result: on-topic asks grounded with correct in-book citations (Ch. 1/2 pages from retrieved provenance); off-topic asks honestly refused with the exact §21 message (one with a separate general-knowledge note). Zero cross-book leakage. Metrics: 6 chat calls, 4.3k prompt / 3.4k completion tokens (completion inflated by reasoning).
- GLM account specifics (recorded so nobody re-probes): free tier — `glm-4.5-flash` works, paid models (glm-4.6/plus/air) 429; embeddings endpoint has NO available model (embedding-3 → 1211). So the live run used fake hash embeddings for the vector side; the LLM generation/citation/honesty behavior — the actual external integration risk — was real.
- Retry-with-error-feedback proved itself live: 2 of 4 asks had empty-content first attempts (reasoning model quirk) and were recovered on attempt 2 by the structured_call loop.
- Credentials live only in gitignored `backend/.env` (z.ai base URL + key + model).

## Recommended Next Step

Product decision: (a) commit the M0–M5 working tree, (b) start Phase 2 (Roadmaps) planning per README §39 Phase 2 + ADR-001. Optional quality items: non-reasoning GLM model or max_tokens tuning to avoid empty-content first attempts; local or alternative embedding provider for a fully-live vector path.
