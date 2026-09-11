# Architecture

Last Verified: 8319ed1 (2026-09-11)

Implementation-facing architecture for the AI Learning Workspace. Spec source: `README.md` §29–38; the README remains the product source of truth.

## 1. System Overview

```text
┌──────────────┐     ┌───────────────────────────┐     ┌─────────────────┐
│  Frontend    │────▶│  Backend API (FastAPI)     │────▶│ PostgreSQL      │
│  Next.js/TS  │◀────│  REST + SSE/WebSocket      │◀────│ + pgvector      │
└──────────────┘     └─────────┬─────────────────┘     └─────────────────┘
                               │ enqueue
                               ▼
                     ┌───────────────────────────┐
                     │  Workers (async jobs)      │──▶ LLMProvider / EmbeddingProvider
                     │  parse · chunk · embed ·   │──▶ ObjectStorage (local → S3)
                     │  extract · roadmap         │
                     └───────────────────────────┘
```

- **Frontend** — Next.js/TypeScript. Dashboard, book workspace, study sessions, recall mode. Talks only to the Backend API.
- **Backend API** — FastAPI. Owns all domain logic, persistence, authorization, and orchestration. Deterministic workflows live here (README §34: no autonomous agents where plain logic suffices).
- **Workers** — background jobs for anything slow or LLM-bound: parsing, chunking, embeddings, concept extraction, roadmap generation. Jobs are idempotent and restartable (README §35).
- **PostgreSQL + pgvector** — single datastore for relational data + vectors (ADR-003).
- **Object storage** — original book files behind a storage abstraction; local filesystem first.

## 2. Interface Boundaries (the load-bearing decision)

All AI/external dependencies sit behind protocols owned by the application (README §30). Business logic depends only on these:

| Interface | Responsibility | Initial adapter |
|---|---|---|
| `LLMProvider` | chat/completion calls, structured-output mode, token accounting | OpenAI-compatible client |
| `EmbeddingProvider` | text → vector; declared dimension + model version | OpenAI-compatible or local sentence-transformers |
| `RetrievalEngine` | top-k semantic search, always filtered by `workspace_id + book_id` | `PgVectorRetrievalEngine` |
| `RoadmapEngine` | concept extraction, dependency building, roadmap drafts | `LLMRoadmapEngine` (ADR-001) |
| `AssessmentEngine` | question generation, rubrics, grading → structured results | `LLMAssessmentEngine` (Phase 4) |
| `ObjectStorage` | put/get/delete book binaries | `LocalStorage` |

Adapters are thin, stateless, and replaceable. No adapter types leak into domain logic.

## 3. Backend Module Layout (target)

```text
backend/
├── app/
│   ├── api/            # FastAPI routers (books, roadmaps, sessions, notes, assessments, recall, search)
│   ├── domain/         # entities, value objects, domain services (pure, framework-free)
│   ├── engines/        # RoadmapEngine, AssessmentEngine implementations
│   ├── llm/            # LLMProvider, EmbeddingProvider + adapters
│   ├── retrieval/      # RetrievalEngine + PgVectorRetrievalEngine
│   ├── storage/        # ObjectStorage + LocalStorage
│   ├── orchestration/  # deterministic pipelines: ingestion, session flow, mastery update
│   ├── persistence/    # SQLAlchemy models, repositories, migrations (Alembic)
│   ├── workers/        # job handlers (shared with workers/ process)
│   └── core/           # config, logging, correlation IDs, errors
├── alembic/            # migrations
└── tests/
```

Workers run the same codebase with a worker entrypoint — no duplicated domain logic.

## 4. Key Flows (deterministic orchestration)

### 4.1 Book Ingestion (Phase 1)

```text
upload → ObjectStorage; book row (status=UPLOADED)
  → job: extract text (PyMuPDF/ebooklib/plain) → detect metadata + TOC → chapters
  → job: semantic chunking → content_chunks (provenance: chapter, page range, section)
  → job: embeddings (content-addressed; skip if hash exists — README §38)
  → job: extractConcepts via RoadmapEngine → concepts
  → job: buildDependencies → concept_relationships
  → book status=READY
```

Each step is a separate idempotent job keyed by `(book_id, stage)`; failure resumes at the failed stage. Re-ingestion never duplicates chunks/concepts (content-hash + unique constraints).

### 4.2 Ask the Book (Phase 1)

```text
question → embed → RetrievalEngine.search(workspace_id, book_id, top_k)
  → LLMProvider with retrieved passages + citation instruction
  → structured response: {answer, citations[], bookGrounded: bool, generalKnowledgeNote?}
```

Insufficient evidence ⇒ explicit "not enough material in this book" response (README §21). General-knowledge additions are a separate, labeled field — never merged into book-grounded text.

### 4.3 Roadmap Generation (Phase 2)

```text
book READY → RoadmapEngine.extractConcepts → concepts (dedup by normalized name + embedding sim)
  → RoadmapEngine.buildDependencies → edges
  → LLMRoadmapEngine.generateRoadmap(concepts, learnerProfile) → RoadmapDraft (validated JSON)
  → orchestrator: roadmap_versions insert (new version, prior untouched), roadmap_nodes persist
```

Regeneration creates a new `roadmap_version`; learner progress maps forward by `concept_id` — history is never destroyed (README §10).

## 5. Cross-Cutting Concerns

- **Book isolation (ADR-002):** every table carries `workspace_id + book_id` where applicable; every repository method and every vector search takes both. Enforced in repositories, not left to callers.
- **Idempotency & restartability:** natural keys + unique constraints (e.g. `(book_id, content_hash)` on chunks; `(roadmap_id, version)`; `(book_id, stage)` job keys).
- **Structured AI outputs:** every persisted AI result passes a Pydantic schema validation step; invalid output ⇒ retry with error feedback, then hard failure surfaced to monitoring.
- **Observability (README §36):** structured JSON logs; correlation ID propagated API → job → LLM call; metrics for durations, token usage, failure counts.
- **Security (README §37):** workspace/user scoping on every query; storage keys namespaced by workspace; no cross-tenant retrieval path exists by construction.
- **Cost (README §38):** content-addressed embeddings, concept extraction skipped when content unchanged, LLM response caching keyed by (prompt template version, model, input hash).
- **Config:** pydantic-settings; all secrets via env (`.env` gitignored). No credentials in code or repo.

## 6. Repository Layout (README §61)

```text
frontend/          Next.js app
backend/           FastAPI app + Alembic
workers/           worker entrypoint (reuses backend code)
tests/             cross-cutting/integration tests (unit tests live with each app)
scripts/           dev/bootstrap utilities
docs/              this documentation + adr/
.ai/               agent context capsule
```
