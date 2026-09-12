# Current Task

Goal: Phase 1 (Book Intelligence) — ALL MILESTONES M0–M5 COMPLETE and verified (2026-09-11).

Why: M5 delivered the README §36 observability subset (in-process JSON metrics at GET /metrics: stage durations/status, chunk counts, embedding + LLM latency, token usage, retrieval latency) and the DoD run (tests/test_dod_e2e.py): 2 different-domain books ingested and asked independently with ZERO cross-book citation leakage, verified per-chunk on real pg16+pgvector. Deviations recorded in docs/adr/004-phase1-build-deviations.md.

Status: Phase 1 DoD met at test level AND confirmed live (2026-09-11): real GLM LLM (glm-4.5-flash via z.ai, key in gitignored backend/.env) answered on-topic questions with correct citations and honestly refused off-topic ones with the §21 message — zero cross-book leakage (scripts/dod_live.py). Embeddings were fake (this GLM account has no embedding model); metrics captured (6 LLM calls, 4.3k prompt / 3.4k completion tokens incl. reasoning). No Phase 2 work starts without an explicit product decision.

Files:

- docs/PHASE1_PLAN.md        (authoritative plan; M0–M5)
- docs/ARCHITECTURE.md       (module layout to scaffold)
- docs/DOMAIN_MODEL.md       (migrations to write in M0)
- docs/adr/*                 (constraints to honor while building)

Completed (bootstrap):

- All §62 artifacts: architecture docs, ADRs 001–003, capsule, schema design, Phase 1 plan, Roadmint analysis

Completed (pre-M1 groundwork):

- First Phase 1 test book ingested manually via `skills/ingest-book` (MarkItDown 0.1.7): Grokking AI Applications (Andrea De Mauro, Manning) → `data/books/grokking-ai-applications/` (manifest + ingestion report). Quality gate: PASS_WITH_WARNINGS — no markdown headings, 0 figures extracted from an illustrated book, no page provenance, code flattened. Source PDF stays untracked under `books/`.

Completed (M0, 2026-09-11):

- `backend/` scaffold: FastAPI app factory (`app/main.py`), pydantic-settings config (`ALW_` prefix, `.env`), JSON structured logging with correlation-ID contextvar, `X-Correlation-ID` middleware (validates/echoes/generates), `GET /health`
- SQLAlchemy 2.0 typed models + Alembic migration `0001` for M0 schema subset: users, workspaces, books, book_sources, chapters, content_chunks, concepts (pgvector `vector(1536)`, HNSW cosine index), learning_events (BRIN on occurred_at)
- Interface protocols + in-memory fakes: `LLMProvider`, `EmbeddingProvider` (app/llm), `RetrievalEngine` (app/retrieval), `RoadmapEngine` extract/build subset (app/engines), `ObjectStorage` (app/storage); retrieval fake enforces workspace+book isolation
- Tooling wired: ruff (E,W,F,I,B,UP), mypy, pytest; unit 15 passed; integration test (`pytest -m integration`, needs TEST_DATABASE_URL) verified migration upgrade/downgrade round-trip on real pg16+pgvector
- Env quirks solved: pip unbootable on this macOS 26.2 + Python 3.14.6 host (`platform.mac_ver()` returns empty → truststore crash) → tooling uses `uv` (brew); venv at `backend/.venv`

Completed (M1, 2026-09-11):

- `POST /workspaces/{ws}/books` (multipart) → sha256 check → LocalStorage key `workspaces/{ws}/books/{id}/source/…` (ADR-002 §4) → book_sources + books(UPLOADED); re-upload same bytes returns existing book (no dup)
- Ingestion chain (`app/orchestration/ingestion/`): PyMuPDFTextExtractor (page-aware, embedded TOC) / PlainTextExtractor; `detect_toc` (TOC conf 0.9, heuristic fallback `Chapter N` regex conf 0.5, synthetic Front matter ordinal 0 when needed); `chunk_document` per RAG §4 (300–600 token target via chars/4, paragraph boundaries, >2-page hard split, chapter-boundary respect, section path from TOC subentries, sha256 content_hash)
- Repositories (isolation-enforced per ADR-002): Workspace/Book/BookSource/Chapter/Chunk — every query filters workspace_id (+book_id); chunks dedup via (book_id, content_hash); stages idempotent (chapters replace_all, chunk insert_new)
- Pipeline: per-stage transactions keyed off books.status (UPLOADED→PARSING→CHUNKED, FAILED stores stage in books.error; re-advance resumes failed stage); API schedules via BackgroundTasks (explicit session.commit before scheduling — teardown ordering lesson)
- Migration 0001 amended: book_sources column is `metadata` (matches DOMAIN_MODEL + ORM mapping), not source_metadata
- Endpoints: POST /books, POST /books/{id}/ingest (resume), GET /books, GET /books/{id} (chapter/chunk counts); workspace existence enforced (404)
- Tests: 31 unit + 4 integration (round-trip dedup, cross-workspace isolation, migration round-trip, resume-from-failure) on pgvector/pgvector:pg16; ruff+mypy clean

Completed (M2, 2026-09-11):

- Migration `0002_concept_relationships` (per DOMAIN_MODEL §2.2; source enum LLM|MANUAL, edge unique `(book_id, from, to, relation)`)
- OpenAI-compatible adapters (`app/llm/openai_compat.py`) on httpx (no SDK): chat/completions (+json response_format) and embeddings (index-sorted); built from settings via `app/llm/factory.py` (returns None when unconfigured)
- `LLMRoadmapEngine` (app/engines/llm_roadmap.py, ADR-001): extract_concepts/build_dependencies against Pydantic schemas (ConceptListOut/RelationshipListOut, camelCase aliases per RAG §2 contract), MAX_ATTEMPTS=3 retry with error feedback then hard fail; normalized-name dedup; unknown refs/self-edges/dup edges dropped; `normalize_name` slugify
- Pipeline stages embed + extract: CHUNKED→EMBEDDED→READY; content-addressed embed (skip on embedding+model match; re-embeds on model change); concepts/edges insert with dedup; stage routing conditioned on configured providers (no providers ⇒ CHUNKED stays terminal, M1 semantics preserved)
- Repos: ConceptRepository / ConceptRelationshipRepository (workspace+book scoped, insert_new returns inserted/skipped)
- Tests: +15 (engine retry/validation, adapter request-shaping via MockTransport, full READY flow, embed idempotency, concept dedup + isolation, resume-from-FAILED@extract); totals: 46 passed unit+integration, ruff+mypy clean

Completed (M3, 2026-09-11):

- Migration `0003_conversations_messages` (kinds ASK_BOOK/TUTOR/DEBUG_MY_UNDERSTANDING; roles; knowledge_source BOOK|LEARNER|SYSTEM per §6/§21)
- `PgVectorRetrievalEngine` (app/retrieval/pgvector_engine.py): cosine distance ordering, hard `workspace_id + book_id` + embedding-not-null filters (ADR-002), returns RetrievedChunk with score
- Shared `app/llm/structured.py::structured_call` (retry-with-error-feedback, MAX_ATTEMPTS=3); LLMRoadmapEngine refactored onto it — engine tests unchanged/green
- `AskService` (app/orchestration/ask.py): retrieve → prompt with passage ids → AskLLMResponse (camelCase aliases) → `intersect_citations` (UUID-canonical; model-claimed ids not in retrieved set are DROPPED — provenance always from retrieved chunks, never model text) → insufficient path returns exact §21 message → persists Conversation + USER/LEARNER + ASSISTANT/BOOK(+citations jsonb) + optional ASSISTANT/SYSTEM note
- API: `POST /workspaces/{ws}/books/{id}/ask` (response_model=AskResult, camelCase), 404 unknown book/workspace, 409 non-READY, 503 providers unconfigured
- Tests: +14 (unit: schema camelCase, intersection, §21 exactness; integration: grounded answer w/ provenance, insufficient contract, invented-citation rejection, cross-book isolation, non-READY guard, endpoint wiring/status mapping). Totals: 53 passed, ruff+mypy clean

Completed (M4, 2026-09-11):

- `frontend/` Next.js 15 App Router + TS (strict), deps: next/react/react-dom only — no UI framework
- Pages: `/` (book list + upload; polls every 2.5s while any book is non-terminal; status pills; FAILED stage+message shown), `/books/[bookId]` (ask chat; citation chips with Ch./pp./section labels; §21 insufficient banner; general-knowledge note rendered as separate labeled block per README §21)
- `src/lib/api.ts` typed client over the existing API (upload multipart, list, get, ask); `NEXT_PUBLIC_API_BASE_URL` + `NEXT_PUBLIC_WORKSPACE_ID` env
- Backend: CORSMiddleware (ALW_CORS_ORIGINS, default localhost:3000); `backend/scripts/bootstrap_workspace.py` creates default workspace `00000000-…-0001`
- Verified: `tsc --noEmit` clean, `next build` clean, live smoke (docker pg16 + uvicorn + next) — frontend HTML served, CORS preflight header present, UI-flow API calls (upload → ingest → list) work; note: without LLM env keys books settle at CHUNKED (capability routing, by design)
- Gotcha: port 3000 is occupied on this dev machine by another app — run UI with `npx next start -p 3100` (or dev on another port)

Completed (M5, 2026-09-11):

- `app/core/metrics.py` (thread-safe counters/histograms/timer) + `GET /metrics`; pipeline stages instrumented via `_instrumented` decorator (ingestion_stage_seconds/total{stage,status}, ingestion_chunks_inserted_total, embedding_seconds); OpenAI adapters record llm_latency_seconds/llm_calls_total/llm_tokens_total{chat|embeddings}; PgVectorRetrievalEngine records retrieval_latency_seconds
- DoD e2e (test_dod_e2e.py): Java-concurrency + Italian-cooking books → ingest to READY → independent asks → all citations resolve to the asked book's chunks only (asserted at retrieval level, result level, and persisted-message level); metrics snapshot verified (each stage ok×2 books)
- ADR-004 records Phase 1 deviations (normalized-name-only concept dedup; capability-based status routing; PyMuPDF over MarkItDown; closed tutor_mode enum; JSON metrics); DECISIONS.md indexed; PHASE1_PLAN verification section updated to actual commands
- Note: DoD used scripted-LLM + fake embeddings (no env keys on this machine); live-LLM run possible anytime ALW_OPENAI_* is provided

Completed (live-LLM DoD, 2026-09-11, scripts/dod_live.py):

- GLM account facts: glm-4.5-flash (free) works on api.z.ai/api/paas/v4; paid models 429 no-balance; NO embedding model available (embedding-3 → 1211 unknown model); glm-4.5-flash is a reasoning model (reasoning_content separate; supports response_format json_object; usage reported)
- Live results: 4 asks — 2 on-topic grounded with correct in-book citations (Ch. 1/2), 2 off-topic honestly refused via §21 (+1 separate general-knowledge note); ZERO cross-book leakage; 6 LLM calls (2 retry-with-feedback recoveries from empty-content first attempts); 4,306 prompt / 3,368 completion tokens
- Known issue: reasoning model sometimes returns empty content on first attempt (2/4 asks needed one retry) — retry loop recovered; consider max_tokens tuning or a non-reasoning model if account gains access

Remaining (Phase 1): nothing — see Known Issues for optional follow-ups
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
- MarkItDown 0.1.7 output for the test book lacks headings/figures/page numbers — M1 must decide whether a page-aware, image-aware extractor (e.g. PyMuPDF-backed `DocumentConverter` adapter) is required to meet the Phase 1 citation DoD

Next Action:

None — Phase 1 complete, live-LLM DoD confirmed. Await product decision: (a) commit the working tree (M0–M5 is a large uncommitted changeset), or (b) begin Phase 2 (Roadmaps) planning. Optional quality follow-up: retry empty-content first attempts or use a non-reasoning GLM model if balance allows.
