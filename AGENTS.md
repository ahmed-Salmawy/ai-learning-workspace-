# AGENTS.md

## Repo State

Design-only repository, past architecture bootstrap (README §62 complete): `README.md` (product spec) + `docs/` (architecture, domain model, RAG design, Phase 1 plan, ADRs 001–003) + `.ai/` capsule all exist and are committed. **No application code yet** — no `backend/`, `frontend/`, `workers/`, no Makefile/package manifests, no CI. Do not scaffold ahead of the current phase; the authoritative next action is always `.ai/CURRENT_TASK.md` (currently: Phase 1 M0 — FastAPI scaffold per `docs/ARCHITECTURE.md` §3, Alembic migrations per `docs/DOMAIN_MODEL.md`).

Untracked working files: `Grokking_AI_Applications.pdf` (first Phase 1 test book — don't commit), `skills/` and `.agents/skills/` (agent skills — don't discard). Never assume a deleted/modified untracked file is recoverable.

## Authority Order (on conflict)

current implementation > accepted ADRs > `.ai/` capsule > older planning docs > README narrative. After resolving a conflict, update the stale source.

## Docs of Record

- `docs/PHASE1_PLAN.md` — milestones M0–M5, build order, verification plan. Authoritative for what to build now.
- `docs/ARCHITECTURE.md` — module layout + interface boundaries; `docs/DOMAIN_MODEL.md` — full schema (source for M0 migrations).
- `docs/adr/001–003` indexed in `.ai/DECISIONS.md` — binding decisions.

## Critical Divergence from README

README §3 suggests Roadmint as the initial roadmap adapter. **ADR-001 overrules this**: Roadmint was inspected in depth (`docs/ROADMAP_ENGINE.md`) and is NOT integrable — GPU-bound fine-tuned model, prose output parsed by regex, no dependency graph/versioning/persistence/tests. The initial adapter is `LLMRoadmapEngine` (schema-validated JSON via `LLMProvider`). Never attempt to integrate Roadmint's code or model; it is conceptual reference only.

## `/wake-up` (when user says `/wake-up` or "wake up", or context was lost)

Full procedure: `skills/wake-up/SKILL.md`. Compact version — run BEFORE making changes:

1. Read `.ai/` capsule in order: `CONTEXT.md`, `PROJECT_STATE.md`, `CURRENT_TASK.md`, `DECISIONS.md`, `DOMAIN_GLOSSARY.md`, `SESSION_HANDOFF.md`.
2. Check git state (`status`, branch, last 10 commits). Never discard uncommitted changes.
3. Resume from `Next Action` in `CURRENT_TASK.md` — never redo completed work.
4. Reply with a short operational summary (phase, current task, next step, risk) — not a repo-wide dump; don't read the whole tree by default.

## End-of-Session Handoff (README §55)

Significant sessions end by updating `PROJECT_STATE.md`, `CURRENT_TASK.md`, `SESSION_HANDOFF.md` (+ `DECISIONS.md`/ADRs if architecture changed). Full procedure: `skills/handoff/SKILL.md`. Every context file needs a `Last Verified: <date/commit>` line. Store distilled engineering state, never conversation transcripts.

## Hard Invariants (README §60 — binding, enforced via ADRs)

- **Book isolation:** every entity and retrieval filters by `workspace_id + book_id`. Cross-book access only when explicitly requested (ADR-002, enforced at repository layer).
- **Immutable learner history:** learner answers/explanations are append-only evidence; AI output never overwrites learner-authored content or historical understanding snapshots.
- **Evidence-based mastery:** mastery comes from assessments/recall/explanations, never reading progress.
- **Provenance:** book-grounded claims retain source (book/chapter/page); never invent citations; explicitly separate book knowledge from general LLM knowledge.
- **Idempotency:** roadmap regeneration and book re-ingestion preserve history and must not create duplicates.
- **Structured AI outputs:** persisted AI results use validated schemas, not prose parsing.
- **Deterministic orchestration preferred:** no autonomous agents where plain app logic suffices.

## Stack & Sequencing

- Planned stack: Next.js/TS frontend, FastAPI/Python backend, PostgreSQL + pgvector in the same DB (ADR-003 — no separate vector DB until justified), background workers, local object storage behind an abstraction.
- All AI/external integrations behind interfaces (`RoadmapEngine`, `LLMProvider`, `EmbeddingProvider`, `RetrievalEngine`, `AssessmentEngine`, `ObjectStorage`). Adapters are swappable; no vendor/tool is a hard dependency.
- Build only the current phase (README §39). Phase 1 = Book Intelligence only — no roadmap/session/assessment UI or tables.

## Skills, Verification & Environment

- Repo-local skills live in `skills/` (`wake-up`, `handoff`, `ingest-book`, `architecture-check`); `.agents/skills/` mirrors all four as identical duplicates — edit `skills/` first, then copy (or edit both). Never discard either copy.
- Verification (none runnable until M0 wires it): `ruff check . && mypy .` then `pytest` — exact form per `docs/PHASE1_PLAN.md`. Integration tests require local Postgres 16 + pgvector via Docker (e.g. `docker run -e POSTGRES_PASSWORD=… pgvector/pgvector:pg16`).
- LLM/embedding credentials come from env (`OPENAI_BASE_URL`/`OPENAI_API_KEY` style) at dev time — never commit keys or `.env` files.
