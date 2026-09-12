# Skill: Architecture Check

## Purpose

Evaluate a proposed or implemented change against the AI Learning Workspace architecture before introducing unnecessary coupling, data leakage, or domain-model erosion.

Invoke:
- before major architectural changes
- when adding a new subsystem/provider
- when modifying book isolation, RAG, roadmap, mastery, assessments, or learning history
- when the user says `/architecture-check`
- when an implementation conflicts with an existing ADR

## Procedure

### 1. Load relevant context

Read:

```text
README.md
.ai/CONTEXT.md
.ai/DECISIONS.md
.ai/CURRENT_TASK.md
docs/ARCHITECTURE.md
docs/DOMAIN_MODEL.md
```

Read only relevant ADRs.

### 2. Define the proposed change

State internally:

```text
Problem
Proposed Change
Affected Modules
Affected Data
External Dependencies
New Coupling
Migration Impact
Failure Modes
```

### 3. Check system invariants

Verify the change preserves:

#### Book Isolation

Book-specific operations must remain scoped by:

```text
workspace_id + book_id
```

Cross-book reasoning must be explicit.

#### Provenance

Book-grounded knowledge retains:
- book
- chapter/section
- page/range when available
- source chunk

AI/general knowledge must not masquerade as book knowledge.

#### Learner History

Never silently overwrite:
- learner explanations
- assessment attempts
- wrong answers
- recall attempts
- mastery history

Historical evidence should remain auditable.

#### Mastery

Reading completion alone must not establish mastery.

Mastery must remain evidence-based and explainable.

#### Roadmap History

Regenerating a roadmap must not destroy historical learning state.

#### Provider Isolation

External providers should remain behind appropriate abstractions such as:

```text
LLMProvider
EmbeddingProvider
RoadmapEngine
AssessmentEngine
RetrievalEngine
```

Provider-specific API calls should not leak throughout domain logic.

#### Structured AI Outputs

Persisted AI domain outputs should use validated schemas.

#### Idempotency

Retrying ingestion, generation, or asynchronous processing must not create uncontrolled duplicate state.

### 4. Evaluate complexity

Ask:

- Can deterministic application logic solve this?
- Does this actually require an autonomous agent?
- Does this introduce another datastore unnecessarily?
- Does this create premature distributed-system complexity?
- Can the existing abstraction support it?
- Is the change reversible?

Prefer the simplest architecture that preserves required invariants.

### 5. Evaluate data model

Check:
- ownership
- foreign keys
- workspace/book scoping
- lifecycle
- versioning
- immutability requirements
- deletion behavior
- indexing
- uniqueness/idempotency constraints

### 6. Evaluate failure behavior

Consider:

```text
LLM timeout
LLM malformed output
duplicate job delivery
partial ingestion
embedding failure
roadmap generation retry
database transaction rollback
stale context
provider outage
```

Important workflows must be retry-safe.

### 7. Decide

Classify:

```text
APPROVE
APPROVE WITH CHANGES
REQUIRES ADR
REJECT
```

Explain only the important architectural reasons.

### 8. Documentation

If architecture materially changes:
- create/update an ADR
- update `.ai/DECISIONS.md`
- update architecture documentation
- update context/handoff files as appropriate

## Guiding Rule

Do not optimize for architectural cleverness.

Optimize for:
- correctness
- isolation
- traceability
- explainability
- maintainability
- incremental evolution
