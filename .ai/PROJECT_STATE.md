# Project State

Last Verified: working tree, uncommitted on top of 18dbe67 (2026-09-11)

Current Phase: Phase 1 (Book Intelligence) COMPLETE — M0–M5 implemented and verified, INCLUDING a live-LLM DoD run (real GLM glm-4.5-flash: on-topic grounded asks cited correctly, off-topic honestly refused, zero leakage). Awaiting product decision on commit / Phase 2.

Completed:

- README spec; AGENTS.md; git repo initialized (main)
- `.ai/` capsule created and maintained
- Roadmint inspected in depth → docs/ROADMAP_ENGINE.md. Verdict: reference only; neither code nor model is integrated (GPU-bound, prose-only output, no dependencies/versioning, naive `lines[1]` PDF extraction)
- docs/ARCHITECTURE.md — components, interface boundaries (LLMProvider, EmbeddingProvider, RetrievalEngine, RoadmapEngine, AssessmentEngine, ObjectStorage), module layout, key flows
- docs/DOMAIN_MODEL.md — full initial schema (all §31 tables) + isolation/idempotency/append-only rules
- docs/RAG_ARCHITECTURE.md — retrieval flow, citation contract, knowledge-source separation
- docs/adr/001 (LLMRoadmapEngine first; Roadmint = reference), 002 (strict book isolation at repository layer), 003 (pgvector, content-addressed embeddings)
- docs/PHASE1_PLAN.md — milestones M0–M5, verification, risks
- First test book ingested manually (skills/ingest-book, MarkItDown 0.1.7): `data/books/grokking-ai-applications/` — PASS_WITH_WARNINGS; source hash recorded; converter limits documented (no headings/figures/page provenance)
- M0 (backend/): FastAPI app factory, pydantic-settings (`ALW_` prefix), JSON logging + correlation-ID middleware, /health; SQLAlchemy 2.0 models + Alembic `0001` (8 core tables, pgvector vector(1536) + HNSW, BRIN learning_events); protocols + fakes for LLMProvider/EmbeddingProvider/RetrievalEngine/RoadmapEngine/ObjectStorage; ruff/mypy/pytest wired (15 unit tests pass); integration test verified migration round-trip on pgvector/pgvector:pg16 via Docker

- M1 (ingestion): upload API + LocalStorage (hash dedup, ADR-002 keys), PyMuPDF page-aware extractor, TOC detection (embedded + heuristic fallback), chapters (incl. synthetic front matter), RAG §4 chunker (content_hash dedup), idempotent/resumable stage pipeline on books.status, isolation-enforced repositories; 4 integration tests on real pg16 (round-trip, isolation, migrations, resume)

- M2 (embeddings + concepts): migration 0002 (concept_relationships), OpenAI-compatible adapters on httpx, LLMRoadmapEngine (schema-validated, bounded retry w/ error feedback), content-addressed embed stage + concept/edge extraction stage (CHUNKED→EMBEDDED→READY), dedup + isolation enforced; +15 tests

- M3 (Ask the Book): migration 0003 (conversations/messages), PgVectorRetrievalEngine (hard-filtered cosine), shared structured_call helper, AskService with citation intersection + §21 insufficient-evidence contract + conversations/messages persistence, POST ask endpoint (404/409/503 mapping); +14 tests

- M4 (minimal UI): frontend/ Next.js 15 App Router + TS strict (next/react only), book list + upload with polling, ask chat with citation chips + labeled general-knowledge notes, typed API client; backend CORS + bootstrap_workspace script; tsc + next build + live smoke verified

- M5 (hardening + DoD): metrics registry + GET /metrics with stage/LLM/retrieval instrumentation; DoD e2e test (2 different-domain books, independent asks, zero cross-book leakage — asserted on retrieval results, ask results, and persisted messages); ADR-004 deviations; plan-doc verification section updated

In Progress: nothing

Not Started:

- Phase 2 (Roadmaps) — not authorized to start without product decision
- Optional: live-LLM DoD confirmation run — DONE 2026-09-11 (scripts/dod_live.py; GLM glm-4.5-flash via z.ai; see CURRENT_TASK)
