# RAG Architecture — "Ask the Book"

Last Verified: 8319ed1 (2026-09-11)

Implements README §21–24. Principle: source-grounded answers with provenance, explicit separation of book knowledge from general LLM knowledge, book isolation enforced at retrieval.

## 1. Retrieval Flow

```text
question
  → query preparation (raw question; optionalHyDE/keyword expansion later, not Phase 1)
  → embed via EmbeddingProvider
  → RetrievalEngine.search(workspace_id, book_id, embedding, top_k=8, filters)
        SQL: WHERE workspace_id = :ws AND book_id = :book
             ORDER BY embedding <=> :q  LIMIT :k        -- pgvector, ADR-003
  → (optional) neighbor expansion: fetch adjacent chunks by (book_id, chapter_id, ordinal)
  → rerank: lightweight heuristic score = vector_sim * 0.8 + section_match * 0.2 (Phase 1; learned reranker deferred)
  → context assembly: top passages + their provenance (chapter, pages, section)
```

## 2. Answer Generation

`LLMProvider` with a fixed prompt contract:

- Answer ONLY from provided passages when they suffice; cite as `(Book title, Ch. N, pp. X–Y)`.
- Each claim must map to a passage ID passed in context.
- If evidence is insufficient: emit `book_grounded = false` + `insufficient_evidence = true` — the API then returns README §21's explicit "could not find enough material in this book" message.
- General-knowledge supplement, when enabled, is a **separate output field** rendered distinctly in UI; never interleaved into book-grounded text.

Response schema (validated before persistence/display):

```json
{
  "answer": "…",
  "bookGrounded": true,
  "citations": [{"chunkId": "…", "bookId": "…", "chapter": 5, "pageStart": 321, "pageEnd": 338, "section": "…"}],
  "insufficientEvidence": false,
  "generalKnowledgeNote": null
}
```

Persisted as a `messages` row with `citations` + `knowledge_source` (docs/DOMAIN_MODEL.md §2.6).

## 3. Guarantees & Rules

1. **Isolation:** every search hard-filters `workspace_id + book_id` inside `PgVectorRetrievalEngine` (ADR-002). Cross-book search exists only as an explicit Phase 6 API path.
2. **No invented citations:** citation list is assembled by intersecting the model's referenced passage IDs with the actually-retrieved set — model-claimed page numbers alone are never trusted.
3. **Never mix knowledge sources silently:** BOOK / LEARNER / SYSTEM provenance is a first-class field end-to-end (README §6).
4. **Cost control:** query embeddings are cheap; generation is capped (max tokens); unchanged books never re-embed (content-addressed, README §38).
5. **Memory layering (README §24):** prompts receive (a) retrieved book passages, (b) a compact learner-profile summary, (c) relevant mastery/misconception notes for the queried concepts — never full conversation transcripts.

## 4. Chunking Strategy (ingestion side)

- Target ~300–600 tokens per chunk, respecting paragraph boundaries; hard page split only when a chunk would span >2 pages.
- Preserve heading path as `section` (e.g. `Ch. 10 > 10.4 volatile`).
- TOC-based chapter detection first; heuristic inference (font-size/numbering via PyMuPDF) as fallback — never Roadmint-style `lines[1]` (docs/ROADMAP_ENGINE.md §2).
- Metadata per chunk: chapter, page range, section, content_hash (embed cache + dedup key).

## 5. Deferred (explicitly)

- Hybrid BM25 + vector fusion (Postgres FTS `tsv` column exists from day 1; fusion scoring lands in Phase 2+).
- Cross-book retrieval, global concepts, knowledge-layer federation (Phase 6).
- Learned rerankers / HyDE / query rewriting — only if Phase 1 evaluation shows retrieval quality gaps.
