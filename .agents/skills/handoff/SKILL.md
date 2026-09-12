# Skill: Handoff

## Purpose

Leave the repository in a state where another AI agent can resume work without needing the previous conversation.

Invoke:
- after meaningful engineering work
- before ending a development session
- before switching agents/models
- when the user says `/handoff`

## Procedure

### 1. Inspect actual state

Before writing the handoff, inspect:

```bash
git status
git diff --stat
git log --oneline -5
```

Run the relevant tests or verification commands when practical.

Do not describe work as complete unless the repository supports that claim.

### 2. Update `.ai/PROJECT_STATE.md`

Record:
- current phase
- completed capabilities
- in-progress capabilities
- not-started major capabilities
- known blockers

Keep this high-level.

### 3. Update `.ai/CURRENT_TASK.md`

Maintain exactly one primary active engineering objective.

Include:

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

`Next Action` must be concrete enough for a fresh agent to execute.

Bad:

```text
Continue backend.
```

Good:

```text
Implement idempotent BookIngestionService.create_chunks() and add integration coverage for reprocessing the same source.
```

### 4. Update `.ai/SESSION_HANDOFF.md`

Use:

```text
# Session Handoff

Date:
...

Worked On:
...

Completed:
...

Important Discoveries:
...

Files Changed:
...

Tests / Verification:
...

Problems / Risks:
...

Recommended Next Step:
...
```

Do not paste raw conversation history.

### 5. Update decisions

If an architectural decision was made:
- update `.ai/DECISIONS.md`
- create/update an ADR when the decision is significant

Record the decision and rationale, not the entire discussion.

### 6. Update stable context only when necessary

Update `.ai/CONTEXT.md` only when stable project facts changed.

Update `.ai/DOMAIN_GLOSSARY.md` only when domain terminology changed.

### 7. Verification marker

Context files should contain:

```text
Last Verified:
<date or git commit>
```

Prefer the current Git commit when available.

## Context quality

Optimize for high-signal machine-readable state.

Good:

```text
Decision:
Use PostgreSQL + pgvector for Phase 1 retrieval.

Reason:
Allows vector search and transactional book_id filtering without another datastore.
```

Avoid narrative transcripts.

## Absolute Rule

A handoff must describe what is true NOW, not what the previous agent intended to do.
