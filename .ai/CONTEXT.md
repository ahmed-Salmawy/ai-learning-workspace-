# Context

Last Verified: 8319ed1 (2026-09-11)

## Product

AI Learning Workspace — an AI-driven Learning Operating System. Turns books into personalized, dependency-aware roadmaps; tracks actual understanding (not reading progress); challenges claimed knowledge with assessments; remembers learning history; detects forgetting; recommends what to learn or recall next.

NOT a "chat with PDF" app. Root spec: `README.md` (authoritative for vision, architecture, data model, agent protocol).

## Architecture (planned — code does not exist yet)

- Frontend: Next.js + TypeScript
- Backend: FastAPI (Python)
- DB: PostgreSQL + pgvector (no separate vector DB)
- Background workers for ingestion/extraction/embeddings/roadmaps
- All AI/external integrations behind interfaces: `RoadmapEngine`, `LLMProvider`, `EmbeddingProvider`, `RetrievalEngine`, `AssessmentEngine`
- Roadmint is at most a `RoadmapEngine` adapter — never a hard dependency (see `docs/ROADMAP_ENGINE.md`)

## Core Invariants (README §60, binding)

1. Books isolated by default; every entity and retrieval filtered by `workspace_id + book_id`
2. Learner answers/explanations immutable (append-only); AI never overwrites learner content
3. Mastery from evidence (assessment/recall/explanations), never reading progress
4. Book-grounded claims retain provenance; never invent citations; book vs general-LLM knowledge kept distinct
5. Roadmap regeneration and re-ingestion preserve history; idempotent
6. Persisted AI outputs use validated structured schemas, not prose parsing
7. Deterministic orchestration preferred over autonomous agents

## Implementation Phases (README §39)

1. Book Intelligence (ingestion, chunks, embeddings, Ask Book, citations)
2. Roadmaps (RoadmapEngine, dependencies, versioning)
3. Learning Workspace (sessions, notes, snapshots)
4. Assessment (generation, grading, mastery)
5. Learning Memory (recall, spaced repetition, recommendations)
6. Cross-Book Intelligence

Current phase: architecture bootstrap (README §62) — no application code yet.

## Workflow Rules

- `/wake-up` protocol: load `.ai/` capsule before changes (see `AGENTS.md`)
- End of significant sessions: update `PROJECT_STATE.md`, `CURRENT_TASK.md`, `SESSION_HANDOFF.md`
- Every context file carries `Last Verified: <commit>`
- Code wins over docs on conflict; update capsule afterward
