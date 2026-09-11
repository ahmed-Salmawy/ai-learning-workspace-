# AGENTS.md

## Repo State

Pre-implementation repository: only `README.md` exists (the full product spec — vision, architecture, data model, agent protocol). No code, no git history, no `.ai/` capsule, no `docs/` yet. Do not assume code exists; if you scaffold it, follow the target layout in README §61 (`frontend/`, `backend/`, `workers/`, `tests/`, `scripts/`, `docs/adr/`, `.ai/`).

## `/wake-up` Protocol (README §40–59)

When the user says `/wake-up` or "wake up", run this BEFORE making changes:

1. Read `README.md`, then `.ai/` capsule files in order: `CONTEXT.md`, `PROJECT_STATE.md`, `CURRENT_TASK.md`, `DECISIONS.md`, `DOMAIN_GLOSSARY.md`, `SESSION_HANDOFF.md`.
2. Inspect git state (`status`, branch, last 10 commits). Never discard uncommitted changes.
3. Resume from `Next Action` in `CURRENT_TASK.md` — never redo completed work.
4. If context files disagree with code: code wins; then update the capsule.
5. Reply with a short operational summary (phase, current task, next step, risk) — not a repo-wide dump. Keep token usage minimal; don't read the whole tree by default.

If `.ai/` doesn't exist yet, the capsule must be created (README §62 Step 5) before substantial application code.

## End-of-Session Handoff (README §55)

Significant sessions must end by updating `PROJECT_STATE.md`, `CURRENT_TASK.md`, `SESSION_HANDOFF.md` (+ `DECISIONS.md`/ADRs if architecture changed). Store distilled engineering state, never conversation transcripts. Every context file needs a `Last Verified: <date/commit>` line.

## Hard Invariants (README §60)

- **Book isolation:** every entity and retrieval filters by `workspace_id + book_id`. Cross-book access only when explicitly requested.
- **Immutable learner history:** original answers/explanations are append-only evidence; AI output never overwrites learner-authored content; never overwrite historical understanding snapshots.
- **Evidence-based mastery:** mastery comes from assessments/recall/explanations, never reading progress.
- **Provenance:** book-grounded claims retain source (book/chapter/page); never invent citations; explicitly separate book knowledge from general LLM knowledge.
- **Idempotency:** roadmap regeneration and book re-ingestion preserve history and must not create duplicates.
- **Structured AI outputs:** persisted AI results use validated schemas, not prose parsing.
- **Deterministic orchestration preferred:** no autonomous agents where plain app logic suffices.

## Stack & Sequencing

- Planned stack (README §29): Next.js/TS frontend, FastAPI/Python backend, PostgreSQL + pgvector (no separate vector DB until justified), background workers, local storage behind an abstraction.
- All AI/external integrations go behind interfaces (`RoadmapEngine`, `LLMProvider`, `EmbeddingProvider`, `RetrievalEngine`, `AssessmentEngine`). Roadmint is only the initial `RoadmapEngine` adapter — never a hard dependency.
- Work follows the phases in README §39; don't build ahead of the current phase. README §62 mandates docs/ADRs/capsule/schema design before substantial code.
