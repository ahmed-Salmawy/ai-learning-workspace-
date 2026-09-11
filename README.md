# AI Learning Workspace

> An AI-driven Learning Operating System that transforms books into personalized learning roadmaps, tracks actual understanding, challenges knowledge through assessments, remembers learning history, and determines what you should learn or recall next.

---

# 1. Vision

This project is NOT another "Chat with PDF" application.

The objective is to build a persistent **AI Learning Operating System**.

A learner uploads one or more books.

The system:

```text
Book
  ↓
Understand Structure
  ↓
Extract Concepts
  ↓
Build Knowledge Graph
  ↓
Generate Learning Roadmap
  ↓
Study
  ↓
Take Notes
  ↓
Explain Understanding
  ↓
Challenge Understanding
  ↓
Assessment
  ↓
Measure Mastery
  ↓
Active Recall
  ↓
Detect Forgetting
  ↓
Adapt Roadmap
```

The AI should permanently understand:

1. What books I am studying.
2. What each book contains.
3. Where I stopped.
4. What concepts I studied.
5. What I claim to understand.
6. Whether testing supports that claim.
7. What notes I wrote.
8. What questions I answered incorrectly.
9. What concepts I consistently struggle with.
10. What concepts I have probably forgotten.
11. What I should study next.
12. How concepts connect across books.

The system should eventually answer questions such as:

> Where did I stop?

> What should I study today?

> What did I learn yesterday?

> What am I weak at?

> What have I probably forgotten?

> Test me on optimistic locking.

> I think I understand volatile. Verify that.

> Why was my previous explanation wrong?

> Give me a 15-minute recall session.

> What does this book say about idempotency?

> Compare what Book A and Book B say about concurrency.

---

# 2. Core Principle

Reading something does NOT mean understanding it.

Completing a chapter does NOT mean mastering it.

The application therefore distinguishes:

```text
READ
  ↓
UNDERSTOOD?
  ↓
EXPLAIN
  ↓
TEST
  ↓
RECALL
  ↓
MASTERED
```

Mastery must come from evidence.

---

# 3. Existing Roadmap Engine

Roadmint can initially be used as a roadmap-generation engine/reference implementation:

https://github.com/Shresht-Ahuja/Roadmint

Roadmint provides useful concepts around:

- PDF roadmap generation
- topic extraction
- LLM roadmap generation
- resource discovery

However, the application MUST NOT tightly couple itself to Roadmint.

Use an abstraction:

```text
RoadmapEngine

generateRoadmap(...)
regenerateRoadmap(...)
extractConcepts(...)
buildDependencies(...)
```

Initial implementation:

```text
RoadmintRoadmapEngine
```

Possible future implementations:

```text
LLMRoadmapEngine
GraphRoadmapEngine
ManualRoadmapEngine
```

The Learning Workspace owns the learning state.

Roadmint is only an engine.

---

# 4. Workspace Architecture

The main hierarchy is:

```text
Workspace
│
├── Book A
│   ├── Source
│   ├── Chapters
│   ├── Concepts
│   ├── Knowledge Graph
│   ├── Roadmap
│   ├── Notes
│   ├── Study Sessions
│   ├── Assessments
│   ├── Recall History
│   └── Mastery State
│
├── Book B
│   ├── Source
│   ├── Chapters
│   ├── Concepts
│   ├── Knowledge Graph
│   ├── Roadmap
│   ├── Notes
│   ├── Study Sessions
│   ├── Assessments
│   ├── Recall History
│   └── Mastery State
│
└── Global Knowledge Layer
    ├── Shared Concepts
    ├── Cross-Book Relationships
    ├── Learner Profile
    └── Global Learning Analytics
```

---

# 5. Book Isolation

This is a critical architectural invariant.

Each book represents an independent learning project.

Example:

```text
Books

├── Java Concurrency in Practice
├── Designing Data-Intensive Applications
├── PostgreSQL Internals
└── Effective Java
```

Knowledge from Book A MUST NOT accidentally contaminate retrieval from Book B.

Every relevant entity must contain:

```text
workspace_id
book_id
```

Including:

- chunks
- concepts
- embeddings
- notes
- questions
- assessments
- conversations
- roadmap nodes
- learning events

Normal retrieval must filter by:

```text
workspace_id + book_id
```

Cross-book retrieval only happens when explicitly requested.

---

# 6. Three Knowledge Sources

Never mix all AI knowledge into one invisible context.

Maintain three distinct knowledge sources.

```text
BOOK KNOWLEDGE
What the author/source says.

YOUR KNOWLEDGE
Notes, explanations, answers and previous attempts.

SYSTEM KNOWLEDGE
General LLM/external knowledge.
```

Example:

User asks:

> Why did I misunderstand volatile?

The system should compare:

```text
My previous explanation
          ↓
Book explanation
          ↓
Concept model
          ↓
Identify discrepancy
          ↓
Explain misconception
```

This is fundamentally different from ordinary RAG.

---

# 7. Book Ingestion

Support initially:

- PDF
- EPUB if practical
- Markdown
- TXT

Pipeline:

```text
Upload
   ↓
Extract Text
   ↓
Detect Metadata
   ↓
Detect Table of Contents
   ↓
Identify Chapters
   ↓
Normalize Content
   ↓
Semantic Chunking
   ↓
Attach Provenance
   ↓
Generate Embeddings
   ↓
Extract Concepts
   ↓
Build Concept Graph
   ↓
Generate Roadmap
```

Each chunk must retain provenance.

Example:

```json
{
  "workspaceId": "...",
  "bookId": "...",
  "chapterId": "...",
  "pageStart": 123,
  "pageEnd": 125,
  "section": "Concurrency",
  "sourceType": "BOOK",
  "text": "..."
}
```

Book-grounded claims must always retain source information.

---

# 8. Concepts

A concept is a learnable knowledge unit.

Examples:

```text
Thread Safety
Atomicity
Visibility
Java Memory Model
Happens-Before
volatile
Optimistic Locking
Pessimistic Locking
MVCC
Idempotency
Outbox Pattern
```

Concepts are not simply chapter headings.

The AI extracts them from content.

---

# 9. Knowledge Graph

Concepts form a graph.

Example:

```text
Race Condition
│
├── related-to → Atomicity
│
├── related-to → Visibility
│
├── prevented-by → Lock
│
└── appears-in
      ├── Java Concurrency
      └── Database Transactions
```

Supported relationships may include:

```text
PREREQUISITE_OF
RELATED_TO
CONTRASTS_WITH
IMPLEMENTED_BY
CAUSES
PREVENTS
EXAMPLE_OF
PART_OF
```

Example learning dependency:

```text
Thread Safety
      ↓
Atomicity
      ↓
Visibility
      ↓
Java Memory Model
   ┌───────┼──────────┐
   ↓       ↓          ↓
volatile  locks  happens-before
                    ↓
              Safe Publication
```

---

# 10. Roadmaps

Roadmaps should NOT simply reproduce chapter order.

The roadmap engine determines:

- prerequisites
- dependencies
- foundational concepts
- important concepts
- optional concepts
- advanced topics
- practical importance
- interview relevance

Example node:

```json
{
  "conceptId": "...",
  "title": "Java Memory Model",
  "status": "IN_PROGRESS",
  "priority": "HIGH",
  "difficulty": 4,
  "estimatedMinutes": 90,
  "prerequisites": [],
  "sourceSections": [],
  "masteryScore": 0.62
}
```

Roadmaps must be versioned.

The system can modify a roadmap when:

- learner already knows something
- learner fails a prerequisite
- learner consistently struggles with something
- learner goal changes
- available study time changes
- interview deadline changes

Roadmap regeneration MUST NOT destroy historical learning data.

---

# 11. Learner Profile

Maintain a global learner profile.

Example:

```text
Role:
Senior / Principal Backend Engineer

Goals:
- Backend engineering interviews
- Distributed systems
- Java concurrency
- PostgreSQL concurrency

Learning Preference:
- practical
- examples first
- interview oriented
- implementation exercises
```

Allow overrides per book.

---

# 12. Study Sessions

The primary learning unit is a Study Session.

Example:

```text
Session
Java Memory Model

Objective:
Understand visibility and happens-before.

Duration:
45 minutes

Material:
Pages 321–338

Concepts:
- visibility
- happens-before
- safe publication
- volatile
```

Session flow:

```text
Recall Previous Knowledge
          ↓
Learn
          ↓
Take Notes
          ↓
Explain in Own Words
          ↓
AI Critique
          ↓
Practice
          ↓
Assessment
          ↓
Update Mastery
          ↓
Schedule Recall
```

Sessions must be resumable.

---

# 13. Notes

Notes may belong to:

```text
Book
Chapter
Concept
Study Session
```

Types:

```text
USER_NOTE
AI_SUMMARY
QUESTION
INSIGHT
CONFUSION
EXAMPLE
CODE
INTERVIEW_NOTE
```

Every note must retain authorship/source:

```text
USER
BOOK
AI
```

Never silently merge them.

Notes must be searchable.

---

# 14. Understanding Snapshots

This is a core feature.

The learner explains a concept in their own words.

Example:

> volatile guarantees that changes to a variable become visible across threads but does not make compound operations atomic.

The AI evaluates it.

Example result:

```text
Understanding Assessment

Correct:
✓ Visibility guarantee
✓ Compound operations aren't automatically atomic

Missing:
- happens-before relationship
- volatile read/write semantics

Potential misconception:
- clarify what operations themselves are atomic

Confidence:
78%
```

Persist:

```text
original explanation
AI evaluation
timestamp
concept
score
missing points
misconceptions
```

Never overwrite historical explanations.

We want to see understanding evolve.

---

# 15. Assertion-Based Learning

The application does not accept:

> I understand optimistic locking.

as proof.

Understanding is treated as a hypothesis.

```text
Learner:
"I understand optimistic locking."

AI:
"Let's verify that."
```

Generate progressively difficult questions.

## Level 1 — Recall

What problem does optimistic locking solve?

## Level 2 — Explanation

Why doesn't optimistic locking require holding a database lock during application business logic?

## Level 3 — Application

Two requests update the same account concurrently.

Show how a version column detects the conflict.

## Level 4 — Failure Analysis

When could optimistic locking perform worse than pessimistic locking?

## Level 5 — Design

Design optimistic locking across five Kubernetes pods.

Only update mastery based on evidence.

---

# 16. Assessment Engine

Support:

```text
Multiple Choice
Short Answer
Explain Concept
Debug Code
Predict Output
Design Question
Scenario
Compare Approaches
Implementation Exercise
Interview Question
```

Persist:

```text
question
learner answer
expected answer/rubric
AI evaluation
score
confidence
concepts tested
difficulty
timestamp
```

Never discard incorrect answers.

Wrong answers are valuable learning data.

---

# 17. Mastery Model

Reading progress != mastery.

Possible initial heuristic:

```text
Mastery =
    Assessment Performance
  + Recall Performance
  + Explanation Quality
  + Practical Exercises
  + Retention Over Time
```

Example:

```text
volatile

Reading            Complete
Notes              Complete
Explanation        82%
Quiz               90%
Recall after 3d    60%

Mastery            74%
```

Start with a transparent deterministic heuristic.

Do NOT introduce ML prematurely.

The system must explain:

> Why is my mastery only 62%?

---

# 18. Active Recall

Previously learned concepts should periodically return without showing the answer first.

Example:

```text
You studied Java Memory Model 4 days ago.

Without checking your notes:

What does happens-before guarantee?
```

After answering:

```text
Your current answer:
...

Your previous answer:
...

Book explanation:
...

Difference:
...

Mastery:
71% → 78%
```

---

# 19. Spaced Repetition

Maintain per concept:

```text
lastReviewedAt
nextReviewAt
reviewCount
successRate
masteryScore
difficulty
```

Weak concepts return sooner.

Strong concepts gradually appear less frequently.

---

# 20. Recall Mode

Support:

```text
Recall 5 minutes
Recall 15 minutes
Recall 30 minutes
```

Concept selection considers:

```text
Low Mastery
+
Time Since Review
+
Concept Importance
+
Previous Mistakes
+
Roadmap Relevance
```

---

# 21. Ask The Book

Provide source-grounded RAG.

Example:

> Why is volatile insufficient for count++?

Answer using retrieved book passages.

Answers should provide:

```text
Book
Chapter
Page
```

Explicitly distinguish:

```text
According to the book...
```

from:

```text
Additional explanation from general knowledge...
```

Never invent citations.

If insufficient book evidence exists:

> I could not find enough material in this book to answer confidently.

General knowledge may then be offered separately.

---

# 22. Search

Global search should cover:

```text
Books
Chapters
Concepts
Notes
Questions
Answers
AI Summaries
Roadmap Nodes
```

Example:

```text
Search:
optimistic locking

Found in:

PostgreSQL Internals
My Notes
Assessment #14
Concurrency Roadmap
```

---

# 23. Cross-Book Knowledge

Books remain isolated by default.

Explicit comparison enables cross-book reasoning.

Example:

> Compare concurrency in Java Concurrency in Practice and Designing Data-Intensive Applications.

Possible graph:

```text
                Concurrency
                /         \
              JVM        Database
              /             \
     Java Memory Model    Transactions
            │                 │
          Locks            Row Locks
```

Global concepts reference source-specific concepts rather than replacing them.

---

# 24. AI Memory Architecture

Separate memory into layers.

## Workspace Memory

Long-lived:

- goals
- learning preferences
- profile

## Book Memory

Book-specific state.

## Session Memory

Current learning interaction.

## Knowledge Memory

Concept mastery and learning history.

Never dump entire historical conversations into prompts.

Retrieve only relevant context.

---

# 25. Recommendation Engine

The dashboard should answer:

> What should I do now?

Example:

```text
Recommended Today

1. Review volatile — 10 min
   Reason:
   Recall overdue + weak retention

2. Continue Chapter 5 — 35 min
   Progress: 67%

3. Retest optimistic locking — 10 min
   Last score: 58%
```

Recommendation logic must be explainable.

---

# 26. Tutor Modes

Support explicit modes:

```text
TEACH
SOCRATIC
TEST
INTERVIEW
RECALL
EXPLAIN
DEBUG_MY_UNDERSTANDING
SUMMARIZE
COMPARE
```

Possible commands:

```text
/test java-memory-model

/recall 15

/interview optimistic-locking

/explain volatile

/challenge-my-understanding
```

---

# 27. Dashboard

Example:

```text
Good Morning

Continue Learning

Java Concurrency in Practice
████████░░░░░░ 37%

Today

3 reviews due
1 weak concept
45 min planned

Books
────────────────────────────

Java Concurrency       37%
DDIA                   12%
PostgreSQL Internals    5%

Knowledge Health
────────────────────────────

Strong       34
Developing   17
Weak          5
```

---

# 28. Book Workspace

Example:

```text
Java Concurrency in Practice

[Roadmap]
[Chapters]
[Concepts]
[Notes]
[Tests]
[Recall]
[Ask Book]
[Progress]

Current
Java Memory Model

Next
Safe Publication

Weak
Atomic Compound Operations
```

---

# 29. Technical Architecture

Recommended initial stack:

## Frontend

```text
Next.js
TypeScript
React
```

## Backend

```text
Python
FastAPI
```

## Database

```text
PostgreSQL
```

## Vector Search

Start with:

```text
PostgreSQL + pgvector
```

Avoid introducing a dedicated vector database until justified.

## Background Processing

Use workers/jobs for:

```text
document parsing
concept extraction
embeddings
roadmap generation
```

## Object Storage

Use an abstraction.

Initial:

```text
Local storage
```

Future:

```text
S3-compatible storage
```

---

# 30. AI Provider Architecture

Never scatter provider-specific calls throughout business logic.

Define abstractions:

```text
LLMProvider

EmbeddingProvider

RoadmapEngine

AssessmentEngine

RetrievalEngine
```

Example:

```text
Application
    │
    ├── RoadmapEngine
    │       └── RoadmintRoadmapEngine
    │
    ├── AssessmentEngine
    │       └── LLMAssessmentEngine
    │
    ├── RetrievalEngine
    │       └── PgVectorRetrievalEngine
    │
    └── LLMProvider
            ├── OpenAIProvider
            └── OtherProvider
```

---

# 31. Core Data Model

Design normalized tables around:

```text
users

workspaces

books
book_sources
chapters
content_chunks

concepts
concept_relationships

roadmaps
roadmap_versions
roadmap_nodes

study_sessions

notes

understanding_snapshots

assessments
assessment_questions
assessment_attempts

concept_mastery
recall_events

conversations
messages

learning_events
```

Use UUID identifiers.

Relevant records must include:

```text
workspace_id
book_id
```

---

# 32. Learning Event Stream

Maintain an append-only learning event stream.

Examples:

```text
BOOK_OPENED

CHAPTER_STARTED

CHAPTER_COMPLETED

CONCEPT_STUDIED

NOTE_CREATED

UNDERSTANDING_SUBMITTED

QUESTION_ATTEMPTED

QUESTION_FAILED

QUESTION_PASSED

RECALL_COMPLETED

MASTERY_CHANGED
```

This enables future analytics without corrupting operational tables.

---

# 33. Structured AI Outputs

Do NOT rely on parsing arbitrary prose.

Use structured outputs.

Example:

```json
{
  "concept": "volatile",
  "score": 0.78,
  "correctPoints": [],
  "missingPoints": [],
  "misconceptions": [],
  "recommendedActions": []
}
```

Validate AI responses before persistence.

---

# 34. Agentic Workflows

Prefer deterministic orchestration.

Example:

```text
Complete Topic
      ↓
Collect Explanation
      ↓
Evaluate Understanding
      ↓
Generate Assessment
      ↓
Grade Assessment
      ↓
Update Mastery
      ↓
Schedule Recall
      ↓
Recommend Next Topic
```

Do NOT create autonomous agents for tasks ordinary application logic can handle reliably.

Use agents when reasoning/tool selection provides clear value.

---

# 35. Engineering Requirements

Follow:

```text
Clean Architecture
SOLID
Clear Module Boundaries
Typed Models
Database Migrations
Unit Tests
Integration Tests
Structured Logging
Idempotency
Retry Safety
```

Document ingestion must be restartable.

Processing the same book again must not create uncontrolled duplicates.

---

# 36. Observability

Measure:

```text
Document ingestion duration

Chunk count

Embedding duration

LLM latency

Token usage

Retrieval latency

Roadmap generation duration

Assessment generation failures

AI grading failures
```

LLM calls should have correlation identifiers.

---

# 37. Security

Books and learner data are private.

Never leak information across:

```text
Users
Workspaces
Books
```

Retrieval must always enforce access boundaries.

---

# 38. Cost Management

Avoid unnecessary LLM work.

Cache expensive outputs where appropriate.

Concept extraction should not rerun when content hasn't changed.

Embeddings should be content-addressed.

Do not regenerate unchanged information.

---

# 39. Implementation Phases

Do NOT attempt the entire system simultaneously.

## Phase 1 — Book Intelligence

Build:

```text
Book upload
Parsing
Semantic chunking
Embeddings
Chapter detection
Concept extraction
Ask Book
Source citations
Book isolation
```

Definition of done:

I can upload multiple books and ask questions against each independently.

## Phase 2 — Roadmaps

Build:

```text
RoadmapEngine abstraction
Roadmint adapter
Concept dependencies
Roadmap generation
Roadmap visualization
Progress tracking
Roadmap versioning
```

Definition of done:

Each book has an independent dependency-aware roadmap.

## Phase 3 — Learning Workspace

Build:

```text
Study sessions
Notes
Concept status
Understanding snapshots
Resume learning
```

Definition of done:

I can leave and return later and the application knows exactly where I stopped.

## Phase 4 — Assessment

Build:

```text
Question generation
Answers
Rubrics
AI grading
Understanding challenges
Mastery model
```

Definition of done:

The system can challenge my claim that I understand a concept.

## Phase 5 — Learning Memory

Build:

```text
Active recall
Spaced repetition
Weak concept detection
Forgetting detection
Recommendation engine
```

Definition of done:

The system can tell me what I should review and why.

## Phase 6 — Cross-Book Intelligence

Build:

```text
Shared concepts
Cross-book search
Cross-book comparisons
Global knowledge graph
```

Definition of done:

The system can reason explicitly across multiple books without corrupting their isolated learning state.

---

# 40. AGENT WAKE-UP SYSTEM

This repository is designed for AI-assisted engineering.

Different AI agents may work on the repository across different sessions.

Agents MUST NOT need to rediscover the entire codebase every time.

The repository therefore maintains an **AI Context Capsule**.

Structure:

```text
.ai/
├── CONTEXT.md
├── PROJECT_STATE.md
├── CURRENT_TASK.md
├── DECISIONS.md
├── DOMAIN_GLOSSARY.md
└── SESSION_HANDOFF.md
```

These files are NOT optional documentation.

They are operational agent memory.

---

# 41. Wake-Up Command

When instructed:

```text
/wake-up
```

or:

```text
wake up
```

the agent MUST execute the following procedure BEFORE making repository changes.

---

# 42. Wake-Up Step 1 — Read README

Read:

```text
README.md
```

This document defines:

```text
Product vision
Architecture
Domain model
Engineering principles
Agent protocol
```

Treat it as the root project context.

---

# 43. Wake-Up Step 2 — Load Context Capsule

Read:

```text
.ai/CONTEXT.md
.ai/PROJECT_STATE.md
.ai/CURRENT_TASK.md
.ai/DECISIONS.md
.ai/DOMAIN_GLOSSARY.md
.ai/SESSION_HANDOFF.md
```

Read them in that order.

Do NOT start implementation before understanding them.

---

# 44. Wake-Up Step 3 — Inspect Git

Execute:

```bash
git status

git branch --show-current

git log --oneline -10
```

Determine:

```text
Current branch
Uncommitted changes
Recent commits
Potential unfinished work
```

Never discard uncommitted changes unless explicitly instructed.

---

# 45. Wake-Up Step 4 — Inspect Architecture

Read selectively:

```text
docs/ARCHITECTURE.md

docs/DOMAIN_MODEL.md

docs/adr/*
```

Then inspect only modules relevant to:

```text
.ai/CURRENT_TASK.md
```

Do NOT recursively read the entire repository unless necessary.

---

# 46. Wake-Up Step 5 — Construct Working Model

Before coding, establish:

```text
Product Goal

Current Phase

Current Architecture

Current Task

Relevant Modules

Relevant Data Model

Important Decisions

Known Constraints

Known Bugs

Next Expected Action
```

---

# 47. Wake-Up Step 6 — Validate Context

Documentation can become stale.

Validate important claims against:

```text
Current Code

Database Migrations

Tests

Git History

Accepted ADRs
```

Priority:

```text
Current Code
    ↓
Accepted ADR
    ↓
Context Capsule
    ↓
Old Planning Documentation
```

If discrepancies exist:

1. identify them
2. determine current truth
3. update the context capsule

---

# 48. Wake-Up Step 7 — Resume

Read:

```text
.ai/CURRENT_TASK.md
```

It should contain:

```text
Goal

Why

Status

Files Involved

Completed

Remaining

Acceptance Criteria

Known Issues

Next Action
```

Continue from:

```text
Next Action
```

Do NOT restart completed work.

---

# 49. Context File — CONTEXT.md

`.ai/CONTEXT.md` contains stable project identity.

Example:

```text
# Context

Last Verified:
<git commit>

Product:
AI Learning Workspace

Purpose:
Turn books into evidence-driven personalized learning journeys.

Architecture:
Next.js + FastAPI + PostgreSQL + pgvector

Core Invariants:

- Books isolated by default
- Mastery evidence based
- Learner history immutable
- Source provenance retained
```

Change rarely.

Target maximum:

~1500 words.

---

# 50. Context File — PROJECT_STATE.md

Tracks implementation status.

Example:

```text
# Project State

Last Verified:
<git commit>

Current Phase:
Phase 2 — Roadmaps

Completed:

✓ PDF ingestion
✓ Semantic chunks
✓ pgvector retrieval
✓ Book isolation

In Progress:

→ Roadmap generation

Not Started:

- Assessments
- Active recall
- Cross-book knowledge
```

Keep concise.

---

# 51. Context File — CURRENT_TASK.md

Contains exactly ONE primary engineering objective.

Example:

```text
# Current Task

Goal:

Implement roadmap generation for an ingested book.

Why:

Roadmaps drive learning sequence.

Status:

RoadmapEngine interface complete.

Roadmint adapter incomplete.

Files:

backend/roadmap/*
backend/books/*

Completed:

✓ RoadmapEngine
✓ domain model

Remaining:

- Roadmint integration
- persistence
- idempotency
- tests

Acceptance Criteria:

Generating the same roadmap twice must not duplicate nodes.

Next Action:

Implement RoadmintRoadmapEngine.generate().
```

---

# 52. Context File — DECISIONS.md

Contains concise architectural decisions.

Example:

```text
# Decisions

ADR-001

Roadmap engines use an adapter interface.

ADR-002

All retrieval must filter by:

workspace_id + book_id

ADR-003

Use PostgreSQL + pgvector initially.

ADR-004

Learning events are append-only.

ADR-005

Mastery uses transparent heuristics initially.
```

Full reasoning belongs in ADRs.

---

# 53. Context File — DOMAIN_GLOSSARY.md

Define domain terminology.

Example:

```text
Book

An independently isolated learning source.

Concept

A learnable knowledge unit extracted from one or more source sections.

Roadmap Node

Representation of a concept inside a particular learning roadmap.

Mastery

Evidence-based estimate of learner understanding.

Understanding Snapshot

Learner explanation plus AI evaluation at a specific point in time.

Recall Event

Attempt to retrieve previously learned knowledge without viewing the source.

Learning Event

Immutable event representing a meaningful learner action.
```

Agents must use these terms consistently.

---

# 54. Context File — SESSION_HANDOFF.md

Updated at the end of meaningful development sessions.

Format:

```text
# Session Handoff

Date:
YYYY-MM-DD

Worked On:
...

Completed:
...

Important Discoveries:
...

Files Changed:
...

Tests:
...

Problems:
...

Recommended Next Step:
...
```

This exists specifically for the next agent.

---

# 55. End-of-Session Protocol

Before ending significant engineering work:

```text
1. Update PROJECT_STATE.md

2. Update CURRENT_TASK.md

3. Update SESSION_HANDOFF.md

4. Update DECISIONS.md if necessary

5. Create/update ADR if architecture changed
```

Do NOT store raw conversation transcripts.

Store distilled engineering state.

---

# 56. Context Compaction

Context files must remain high signal.

Good:

```text
Decision:
Use pgvector.

Reason:
Allows transactional metadata and vector filtering by book_id without another datastore.
```

Bad:

```text
We had a long discussion about different databases and then considered...
```

Optimize for rapid machine comprehension.

---

# 57. Token Discipline

Wake-up must be context-efficient.

Do NOT automatically read:

```text
Entire source tree

Entire test suite

Entire git history

Every historical ADR

Old conversations
```

Start with:

```text
README
+
Context Capsule
+
Current Git State
```

Expand only when necessary.

---

# 58. Stale Context Detection

Every context file must contain:

```text
Last Verified:
<date or git commit>
```

If context disagrees with implementation:

```text
CODE WINS
```

Update documentation afterward.

---

# 59. Wake-Up Response

After executing wake-up, output only a concise operational summary.

Example:

```text
Workspace understood.

Current Phase:
Assessment Engine

Current Task:
Persist assessment attempts and update concept mastery.

Relevant Architecture:
AssessmentService
MasteryService
PostgreSQL

Last Completed:
Question generation and rubric grading.

Next:
Implement mastery update after graded attempt.

Risk:
Mastery updates must remain idempotent.
```

Then continue the requested work.

Do NOT produce a giant repository summary unless requested.

---

# 60. Absolute System Invariants

These rules MUST NOT be violated.

### Invariant 1

Books are isolated by default.

### Invariant 2

Book retrieval enforces:

```text
workspace_id + book_id
```

### Invariant 3

Original learner answers are immutable historical evidence.

### Invariant 4

AI interpretations never overwrite learner-authored content.

### Invariant 5

Book-grounded statements retain source provenance.

### Invariant 6

Mastery comes from evidence, not reading completion.

### Invariant 7

Roadmap regeneration preserves historical learning state.

### Invariant 8

Learning history is never silently discarded.

### Invariant 9

Context files represent current truth, not historical plans.

### Invariant 10

Significant engineering sessions end with an agent handoff.

### Invariant 11

External/system knowledge must not silently masquerade as book knowledge.

### Invariant 12

AI outputs persisted as domain data must use validated structured schemas.

---

# 61. Initial Repository Structure

Target:

```text
ai-learning-workspace/
│
├── README.md
│
├── frontend/
│
├── backend/
│
├── workers/
│
├── tests/
│
├── scripts/
│
├── docs/
│   │
│   ├── ARCHITECTURE.md
│   ├── DOMAIN_MODEL.md
│   ├── ROADMAP_ENGINE.md
│   ├── RAG_ARCHITECTURE.md
│   │
│   └── adr/
│       ├── 001-roadmap-engine-abstraction.md
│       ├── 002-book-isolation.md
│       └── 003-vector-storage.md
│
└── .ai/
    ├── CONTEXT.md
    ├── PROJECT_STATE.md
    ├── CURRENT_TASK.md
    ├── DECISIONS.md
    ├── DOMAIN_GLOSSARY.md
    └── SESSION_HANDOFF.md
```

---

# 62. First Agent Assignment

Before implementing substantial application code:

## Step 1

Study this README completely.

## Step 2

Inspect the Roadmint repository.

Determine:

```text
Architecture

Reusable modules

Roadmap generation flow

PDF processing

LLM integration

Resource discovery

Dependencies

Integration risks
```

## Step 3

Document the proposed architecture.

Create:

```text
docs/ARCHITECTURE.md

docs/DOMAIN_MODEL.md

docs/ROADMAP_ENGINE.md

docs/RAG_ARCHITECTURE.md
```

## Step 4

Create ADRs:

```text
001-roadmap-engine-abstraction.md

002-book-isolation.md

003-vector-storage.md
```

## Step 5

Create the `.ai` context capsule.

## Step 6

Design the database schema.

## Step 7

Propose implementation packages/modules.

## Step 8

Produce a Phase 1 implementation plan.

## Step 9

Only then begin implementation.

---

# 63. Definition of Product Success

The product succeeds when I can upload a technical book and later ask:

> Where did I stop?

and the system knows.

I can say:

> I understand optimistic locking.

and the system challenges that assertion.

I can say:

> Test me.

and it knows what to test.

I can return three weeks later and ask:

> What have I forgotten?

and the system answers using learning evidence.

I can ask:

> Why do I keep getting this concept wrong?

and the system analyzes my historical explanations and assessments.

I can upload another book without corrupting the first book's:

```text
roadmap
notes
concepts
assessments
mastery
recall history
```

I can explicitly ask:

> Compare these two books.

and cross-book reasoning becomes available.

Finally, a completely fresh coding agent should be able to enter the repository, execute:

```text
/wake-up
```

and understand:

```text
What we are building

Why we are building it

How it is architected

What has already been implemented

What decisions have been made

What is currently being worked on

What should happen next
```

without rereading the entire repository or requiring the previous agent's conversation history.

---

# 64. Guiding Principle

The goal is not:

> Help me read books.

The goal is:

> Build a persistent AI system that understands what I am trying to learn, knows what I actually understand, remembers where my understanding fails, challenges me until the knowledge is demonstrated, and continuously determines the most valuable thing for me to learn or recall next.

Build every feature against that principle.
