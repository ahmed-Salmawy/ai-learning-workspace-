# ADR-002: Book Isolation — `workspace_id + book_id` Scoping on Every Learning Entity

Date: 2026-09-11
Status: Accepted
Decides README §5, §37, §60 (Invariants 1–2).

## Context

Each book is an independent learning project. Knowledge from Book A must never contaminate Book B's retrieval, roadmaps, mastery, or recommendations. A single missing `WHERE book_id = …` clause is enough to silently corrupt learning state — the most dangerous class of bug in this product. Cross-book reasoning is a legitimate future feature (README §23) but must be explicit, never accidental.

## Decision

1. Every learning-scoped table carries `workspace_id`, and every book-scoped table additionally carries `book_id` — both `NOT NULL` and indexed (see docs/DOMAIN_MODEL.md).
2. Repository methods are the only DB access path; each repository takes `(workspace_id, book_id)` scoping parameters and applies them to **every** query, including vector search (`PgVectorRetrievalEngine` hard-filters before the ANN search).
3. Cross-book retrieval exists only as an explicit API surface (Phase 6) that takes a deliberate list of book IDs; no code path widens scope implicitly.
4. Object storage keys are namespaced `workspaces/{workspace_id}/books/{book_id}/…`.
5. Reviewer rule for PRs: any new query on a learning table without explicit scope constants is a defect.

## Consequences

- Slight duplication of scope columns/parameters everywhere; accepted as the price of a default-safe design.
- Enforced at the repository layer first; Postgres Row-Level Security is a later hardening step when multi-user deployment approaches (deferred in DOMAIN_MODEL §4).
- Global/cross-book knowledge (Phase 6) will *reference* book concepts rather than merge them (README §23: global concepts reference source-specific concepts).
