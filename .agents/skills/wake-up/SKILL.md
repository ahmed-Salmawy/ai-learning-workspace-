# Skill: Wake Up

## Purpose

Reconstruct the current engineering context quickly and safely before making repository changes.

Invoke when:
- starting a new agent session
- the user says `/wake-up`, `wake up`, or equivalent
- context was compacted/lost
- switching agents/models
- current project state is unclear

## Procedure

### 1. Read root instructions

Read, when present:

```text
README.md
AGENTS.md
```

Treat repository instructions as authoritative.

### 2. Load the AI context capsule

Read in order:

```text
.ai/CONTEXT.md
.ai/PROJECT_STATE.md
.ai/CURRENT_TASK.md
.ai/DECISIONS.md
.ai/DOMAIN_GLOSSARY.md
.ai/SESSION_HANDOFF.md
```

Missing files are project-state information. Do not invent their contents.

### 3. Inspect Git

Run:

```bash
git status
git branch --show-current
git log --oneline -10
```

If the directory is not a Git repository, report that clearly.

Never discard uncommitted work unless explicitly instructed.

### 4. Determine current state

Establish:

```text
Product Goal
Current Phase
Current Task
Last Completed Work
Relevant Architecture
Relevant Modules
Important Decisions
Known Constraints
Known Problems
Next Action
```

### 5. Validate documentation

Context files may be stale.

Validate important claims against:
- current code
- database migrations
- tests
- accepted ADRs
- recent Git history

Priority when information conflicts:

```text
Current implementation
    ↓
Accepted ADRs
    ↓
Current context capsule
    ↓
Older planning documentation
```

Do not silently ignore discrepancies. Correct stale context when appropriate.

### 6. Inspect only relevant code

Use `.ai/CURRENT_TASK.md` to determine which modules matter.

Do not recursively read the entire repository unless genuinely necessary.

### 7. Resume

Continue from the `Next Action` in `.ai/CURRENT_TASK.md`.

Do not restart completed work.

If `CURRENT_TASK.md` does not exist, derive the next action from the repository's authoritative bootstrap instructions.

## Output

After wake-up, provide a compact operational summary:

```text
Wake-up complete.

Phase:
...

Current Task:
...

Last Completed:
...

Relevant Architecture:
...

Next:
...

Risks:
...
```

Then continue requested work when the next action is unambiguous.

Do not repeatedly ask for confirmation for routine reversible engineering steps.

Ask only when:
- product direction would materially change
- an irreversible/high-impact architecture decision is required
- credentials/secrets are required
- requirements genuinely conflict
- the next action cannot be derived safely

## Invariants

- Never invent project state.
- Never discard uncommitted work.
- Never treat stale documentation as more authoritative than current implementation.
- Keep context loading selective and token-efficient.
- Resume rather than restart.
