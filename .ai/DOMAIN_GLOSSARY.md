# Domain Glossary

Last Verified: 8319ed1 (2026-09-11)

Use these terms consistently in code, docs, and AI outputs.

- **Workspace** — top-level container; owns books, learner profile, global knowledge layer.
- **Book** — an independently isolated learning source (PDF/EPUB/MD/TXT). Isolation boundary for all retrieval.
- **Book Source** — original uploaded file + metadata + storage reference.
- **Chapter** — detected structural unit of a book (from TOC or inference).
- **Content Chunk** — semantically coherent text span with provenance (book, chapter, page range, section) and an embedding.
- **Concept** — a learnable knowledge unit extracted from content (not a chapter heading). Has graph relationships.
- **Concept Relationship** — typed edge between concepts: PREREQUISITE_OF, RELATED_TO, CONTRASTS_WITH, IMPLEMENTED_BY, CAUSES, PREVENTS, EXAMPLE_OF, PART_OF.
- **Knowledge Graph** — concepts + relationships scoped to a book (plus a global layer for cross-book, later phases).
- **Roadmap** — versioned, dependency-aware learning sequence over a book's concepts. NOT chapter order.
- **Roadmap Node** — a concept inside a particular roadmap version (status, priority, difficulty, estimate, prerequisites).
- **Study Session** — primary learning unit; resumable; has objective, material, concepts, flow (recall → learn → notes → explain → critique → practice → assess → schedule).
- **Note** — user/AI/book-authored note; must retain authorship (USER | BOOK | AI); never silently merged.
- **Understanding Snapshot** — learner's own explanation + AI evaluation at a point in time. Append-only history.
- **Assessment / Attempt** — generated question set / a learner's graded pass through it. Wrong answers are kept as learning data.
- **Mastery** — evidence-based estimate of understanding (assessments + recall + explanations + exercises + retention). Deterministic heuristic first.
- **Recall Event** — attempt to retrieve previously learned knowledge without viewing the source.
- **Spaced Repetition State** — per-concept scheduling: lastReviewedAt, nextReviewAt, reviewCount, successRate, difficulty.
- **Learning Event** — immutable event in the append-only learning event stream (e.g. QUESTION_FAILED, MASTERY_CHANGED).
- **Provenance** — source trace for book-grounded content: book/chapter/page range/section. Never invented.
- **Knowledge Source Type** — BOOK | LEARNER | SYSTEM; three knowledge layers that must never be silently mixed.
