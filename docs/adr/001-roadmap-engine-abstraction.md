# ADR-001: Roadmap Engine Abstraction — LLM-Backed Engine First, Roadmint as Reference Only

Date: 2026-09-11
Status: Accepted
Decides README §3 / §30 / §62 Step 2. Evidence: docs/ROADMAP_ENGINE.md (Roadmint code inspection, HEAD e03afce).

## Context

README §3 proposed `RoadmintRoadmapEngine` as the initial `RoadmapEngine` implementation. Deep inspection of Roadmint found:

- Output is unstructured plain text parsed by regex — violates the structured-outputs invariant (README §33).
- Its "PDF topic extraction" is the 2nd line of each page (`pdf_mode.py:15`) — a slide-deck heuristic, unusable for books.
- No dependency graph, no prerequisites, no roadmap versioning — core requirements (README §10).
- Fine-tuned Gemma-2B requires CUDA + bitsandbytes 4-bit quantization; not deployable in the planned stack.
- It is a Streamlit demo, not a library (no package, no tests, no persistence).

## Decision

1. `RoadmapEngine` is a formal protocol (`generateRoadmap`, `regenerateRoadmap`, `extractConcepts`, `buildDependencies`) returning **validated structured drafts** (Pydantic), never prose.
2. The **initial adapter is `LLMRoadmapEngine`**: `LLMProvider` + schema-validated JSON output + structure validation (completeness of nodes/edges/time estimates — idea borrowed from Roadmint's evaluator).
3. **Roadmint is not integrated as code or model.** It is retained as conceptual reference (interface shape, negative PDF lesson, roadmap-quality scoring ideas). A `RoadmintRoadmapEngine` adapter may be built later only if a GPU runtime and a structured-output wrapper make it viable.

## Consequences

- Phase 2 has no GPU/model-hosting requirement; roadmap quality depends on prompt + schema engineering behind `LLMProvider` (provider-swappable).
- Slight divergence from README §3's *suggested* initial adapter; the abstraction requirement (§3 "MUST NOT tightly couple") is honored, and `LLMRoadmapEngine` was explicitly listed as a possible implementation. Flagged to product owner in SESSION_HANDOFF.
- Concept extraction and dependency building share the same engine boundary, so a future Roadmint/Graph/Manual engine can replace generation without touching ingestion callers — but only if it also implements the full protocol.
