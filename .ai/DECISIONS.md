# Decisions

Last Verified: 8319ed1 (2026-09-11)

ADR index (full reasoning in `docs/adr/`):

- ADR-001 — Roadmap engines use a `RoadmapEngine` adapter interface; initial adapter is LLM-backed with structured output, NOT Roadmint's fine-tuned model (GPU-bound, prose-only output). Roadmint = conceptual reference. (`docs/adr/001-roadmap-engine-abstraction.md`)
- ADR-002 — Strict book isolation: all learning entities carry `workspace_id + book_id`; retrieval enforces the filter; cross-book only via explicit request path. (`docs/adr/002-book-isolation.md`)
- ADR-003 — Vector storage: PostgreSQL + pgvector in the same DB as relational data; no separate vector DB until a justified need exists. Embeddings content-addressed (hash of normalized chunk text). (`docs/adr/003-vector-storage.md`)

- ADR-004 — Phase 1 build deviations: concept dedup = normalized_name only (sim-dedup deferred to Phase 2); capability-based pipeline status routing (CHUNKED terminal without providers); PyMuPDF extraction over MarkItDown; closed tutor_mode enum; in-process JSON metrics. (`docs/adr/004-phase1-build-deviations.md`)

Other significant decisions (no ADR unless architecture-level):

- Roadmint verdict: reuse neither its code nor its model. Valuable only as: interface shape precedent, PDF-heuristic cautionary tale, roadmap-quality evaluation ideas (structure scoring, semantic similarity). Detail: `docs/ROADMAP_ENGINE.md`.
- Phase 1 LLM provider: any OpenAI-compatible API behind `LLMProvider` interface; concrete provider chosen at implementation time via env config (no credentials committed).
- Mastery: deterministic transparent heuristic (weighted evidence sum) before any ML — README §17.
- IDs: UUIDs everywhere (README §31).
- Learning event stream: append-only `learning_events` table from day 1 (README §32).
