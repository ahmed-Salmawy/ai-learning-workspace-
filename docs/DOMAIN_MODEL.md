# Domain Model & Initial Database Schema

Last Verified: 8319ed1 (2026-09-11)

Implements README §31–32, §5 (book isolation), §14 (snapshots), §17 (mastery), §19 (spaced repetition). Schema is design-only at this point — Alembic migrations come with Phase 1 implementation.

Conventions: UUID PKs; `created_at/updated_at timestamptz` on every table (omitted below for brevity); all learning-scoped tables carry `workspace_id` and (where book-scoped) `book_id` — **NOT NULL, indexed, always part of retrieval filters (ADR-002)**.

## 1. Entity Overview

```text
Workspace 1─* Book 1─1 BookSource
                     1─* Chapter 1─* ContentChunk
                     1─* Concept 1─* ConceptRelationship (edges within book)
                     1─* Roadmap 1─* RoadmapVersion 1─* RoadmapNode
                     1─* StudySession
                     1─* Note
                     1─* UnderstandingSnapshot
                     1─* Assessment 1─* AssessmentQuestion 1─* AssessmentAttempt
                     1─* RecallEvent
                     1─* Conversation 1─* Message
                     1─* LearningEvent (append-only)
Workspace 1─1 LearnerProfile
Concept (book-scoped) 1─0..1 ConceptMastery 1─* RecallEvent
Global layer (Phase 6): GlobalConcept ── references ──▶ per-book Concepts
```

## 2. Tables

### 2.1 Identity & Workspace

```text
users            id, email (unique), display_name
workspaces       id, owner_user_id → users, name
learner_profiles id, workspace_id (unique), role, goals jsonb, preferences jsonb
```

### 2.2 Books & Content

```text
book_sources     id, workspace_id, book_id, storage_key, original_filename,
                 mime_type, file_hash (unique per workspace), page_count, metadata jsonb

books            id, workspace_id, title, author, status
                 (UPLOADED|PARSING|CHUNKED|EMBEDDED|READY|FAILED), error jsonb, ingested_at

chapters         id, workspace_id, book_id, ordinal, title, page_start, page_end,
                 source (TOC|INFERRED), unique (book_id, ordinal)

content_chunks   id, workspace_id, book_id, chapter_id, ordinal,
                 text, section, page_start, page_end,
                 content_hash,                      -- normalized-text hash; embed cache key
                 embedding vector(1536),            -- pgvector; dimension per EmbeddingProvider (ADR-003)
                 embedding_model, token_count,
                 unique (book_id, content_hash)
                 index ivfflat/hnsw on (embedding) with workspace_id equality filter

concepts         id, workspace_id, book_id, name, normalized_name, description,
                 embedding vector(1536),
                 unique (book_id, normalized_name)  -- re-ingestion dedup (idempotency invariant)

concept_relationships
                 id, workspace_id, book_id, from_concept_id, to_concept_id,
                 relation (PREREQUISITE_OF|RELATED_TO|CONTRASTS_WITH|IMPLEMENTED_BY|
                           CAUSES|PREVENTS|EXAMPLE_OF|PART_OF),
                 source (LLM|MANUAL), confidence numeric,
                 unique (book_id, from_concept_id, to_concept_id, relation)
```

### 2.3 Roadmaps

```text
roadmaps         id, workspace_id, book_id, active_version_id (nullable FK)

roadmap_versions id, workspace_id, book_id, roadmap_id, version_number,
                 reason (INITIAL|PROGRESS|STRUGGLE|GOAL_CHANGE|TIME_CHANGE|MANUAL),
                 generated_by (engine name + model), created_at,
                 unique (roadmap_id, version_number)   -- regeneration appends, never mutates (README §10)

roadmap_nodes    id, workspace_id, book_id, roadmap_version_id, concept_id,
                 ordinal, status (LOCKED|AVAILABLE|IN_PROGRESS|COMPLETED|SKIPPED),
                 priority, difficulty int 1..5, estimated_minutes,
                 mastery_score numeric,               -- denormalized read-model, refreshed from concept_mastery
                 unique (roadmap_version_id, concept_id)

roadmap_node_prerequisites
                 roadmap_version_id, node_id, prerequisite_node_id,
                 pk (roadmap_version_id, node_id, prerequisite_node_id)
```

### 2.4 Learning: Sessions, Notes, Snapshots

```text
study_sessions   id, workspace_id, book_id, roadmap_node_id (nullable), objective,
                 status (PLANNED|ACTIVE|PAUSED|COMPLETED|ABANDONED),
                 planned_minutes, started_at, ended_at, resume_state jsonb   -- §12 resumable

notes            id, workspace_id, book_id, chapter_id (null), concept_id (null),
                 study_session_id (null), note_type (USER_NOTE|AI_SUMMARY|QUESTION|INSIGHT|
                           CONFUSION|EXAMPLE|CODE|INTERVIEW_NOTE),
                 authorship (USER|BOOK|AI),          -- never silently merged (README §13)
                 title, body, embedding vector(1536), tsv tsvector (FTS)

understanding_snapshots                                -- APPEND-ONLY (README §14)
                 id, workspace_id, book_id, concept_id, study_session_id (null),
                 learner_explanation text,             -- immutable original
                 evaluation jsonb (validated schema: correct/missing/misconceptions/confidence),
                 confidence numeric, evaluated_at
                 -- no UPDATE path; corrections are new snapshots
```

### 2.5 Assessment & Mastery

```text
assessments      id, workspace_id, book_id, concept_ids uuid[], kind
                 (SESSION|CHALLENGE|RECALL|INTERVIEW), status, generated_by jsonb

assessment_questions
                 id, workspace_id, assessment_id, concept_id, ordinal,
                 question_type (MCQ|SHORT_ANSWER|EXPLAIN|DEBUG_CODE|PREDICT_OUTPUT|DESIGN|
                                SCENARIO|COMPARE|IMPLEMENTATION|INTERVIEW),
                 question, options jsonb (null), expected_answer, rubric jsonb,
                 difficulty int 1..5, level int 1..5               -- §15 assertion levels

assessment_attempts                                    -- APPEND-ONLY evidence (README §16)
                 id, workspace_id, assessment_question_id, learner_answer text,
                 ai_evaluation jsonb (validated: score/feedback/misconceptions),
                 score numeric, is_correct bool, answered_at

concept_mastery  id, workspace_id, book_id, concept_id,
                 mastery_score numeric, components jsonb,  -- transparent breakdown §17
                 lastReviewedAt, nextReviewAt, reviewCount, successRate, difficulty,
                 unique (book_id, concept_id)

recall_events    id, workspace_id, book_id, concept_id, prompt, mode_minutes,
                 learner_answer, evaluation jsonb, score numeric, recalled_at
```

### 2.6 Conversations & Event Stream

```text
conversations    id, workspace_id, book_id, kind (ASK_BOOK|TUTOR|DEBUG_MY_UNDERSTANDING),
                 tutor_mode (TEACH|SOCRATIC|TEST|INTERVIEW|RECALL|EXPLAIN|...|null)
messages         id, workspace_id, conversation_id, role (USER|ASSISTANT|SYSTEM),
                 content, citations jsonb,               -- {book_id,chapter,page,section,chunk_id}
                 knowledge_source (BOOK|LEARNER|SYSTEM)  -- §6/§21 separation

learning_events                                        -- APPEND-ONLY (README §32)
                 id, bigserial seq, workspace_id, book_id (null), concept_id (null),
                 event_type (BOOK_OPENED|CHAPTER_STARTED|...|MASTERY_CHANGED),
                 payload jsonb, occurred_at
                 BRIN index on (occurred_at); never updated or deleted
```

## 3. Isolation & Integrity Rules (enforced in repositories + constraints)

1. Every SELECT/UPDATE/DELETE for learning-scoped tables filters `workspace_id` (+ `book_id` for book-scoped) — repository-layer mandate, ADR-002.
2. Append-only tables (`understanding_snapshots`, `assessment_attempts`, `recall_events`, `learning_events`): no UPDATE/DELETE grants in app role; inserts only.
3. Idempotency keys: `content_chunks(book_id, content_hash)`, `concepts(book_id, normalized_name)`, `roadmap_versions(roadmap_id, version_number)` — re-runs dedupe instead of duplicating (README §35).
4. Embedding dimension is a single deployment-wide constant matching `EmbeddingProvider`; changing providers requires a migration + re-embed job (tracked via `embedding_model` column).
5. Mastery changes flow: evidence event → deterministic mastery service → `concept_mastery` upsert + `learning_events(MASTERY_CHANGED)` + roadmap node score refresh — in one transaction.

## 4. Deliberately Deferred

- Row-level security (single-user deployment initially; repository enforcement first, RLS when multi-user hardening begins — tracked for Phase 4+).
- `global_concepts` and cross-book tables (Phase 6) — schema sketched in entity overview only.
- Partitioning of `learning_events` (revisit after volume exists).
