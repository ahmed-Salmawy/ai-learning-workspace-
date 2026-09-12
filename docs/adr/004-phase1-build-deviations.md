# ADR-004: Phase 1 Build Deviations and Clarifications

Date: 2026-09-11
Status: Accepted
Decides: deviations discovered while implementing M0–M5 (docs/PHASE1_PLAN.md), recorded per M5 step 3.

## Context

The Phase 1 plan and DOMAIN_MODEL were written before implementation. Building M0–M4 surfaced a small number of places where the docs' letter and the built system differ, or where the docs left the semantics open. These are not architecture changes; they are recorded so the docs can be reconciled and future agents are not surprised.

## Decisions

1. **Concept dedup is `normalized_name` only in Phase 1.** DOMAIN_MODEL §4.3 (architecture flow) says concepts dedupe "by normalized name + embedding sim". Phase 1 implements normalized-name dedup (unique constraint `(book_id, normalized_name)`); embedding-similarity dedup is deferred to Phase 2, where concept embeddings and roadmap regeneration need them anyway. Rationale: sim-dedup without concept embeddings would add an embedding job for marginal benefit at Phase 1 volumes.

2. **Pipeline stage routing is capability-based.** `books.status` lifecycle (UPLOADED → PARSING → CHUNKED → EMBEDDED → READY) advances only through stages whose required provider is configured: without `EmbeddingProvider`/`LLMProvider` env config, CHUNKED is the terminal state and the book is usable for text-level workflows; with providers, the pipeline continues to EMBEDDED and READY. This keeps M1 semantics valid without credentials while enabling the full chain — DOMAIN_MODEL's status list is unchanged.

3. **Extraction is PyMuPDF-based, not MarkItDown-based.** The manual MarkItDown pilot (`skills/ingest-book`, see SESSION_HANDOFF) lost page provenance, figures, and heading structure for the Phase 1 test book. The plan already specified "extract text (PyMuPDF for PDF)"; MarkItDown remains at most an alternate `TextExtractor` adapter, never the default. Page-aware extraction is what makes the Phase 1 citation contract possible.

4. **`tutor_mode` is a closed varchar+check enum of 6 values** (TEACH, SOCRATIC, TEST, INTERVIEW, RECALL, EXPLAIN) instead of the doc's open-ended list; extending it is a migration, same as other enums.

5. **Metrics are an in-process JSON registry** (`/metrics`), not Prometheus format — README §36's subset (stage durations, chunk counts, LLM latency/token usage, retrieval latency) is satisfied; a Prometheus exposition is a mechanical follow-up when an external scraper exists.

## Consequences

- DOMAIN_MODEL §2.2 concept-dedup note and §3.4 remain accurate for storage; the "embedding sim" clause moves to Phase 2 scope.
- Operators deploying Phase 1 without LLM keys get a functioning ingestion pipeline that stops at CHUNKED; `/metrics` and `books.error` make the state visible.
