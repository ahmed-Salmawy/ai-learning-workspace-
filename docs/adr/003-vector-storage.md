# ADR-003: Vector Storage — PostgreSQL + pgvector, No Separate Vector DB

Date: 2026-09-11
Status: Accepted
Decides README §29 (Vector Search) / §62.

## Context

The system needs semantic search over content chunks, concepts, and notes. Options: dedicated vector DB (Pinecone, Qdrant, Milvus, Weaviate) or pgvector inside the primary PostgreSQL.

The decisive requirement is **filtered ANN search**: every vector query must hard-filter `workspace_id + book_id` (ADR-002). With a separate vector DB, that means either syncing relational metadata out-of-band (dual-write consistency risk) or doing post-filtering (correctness/perf hazards). With pgvector, scope filtering and ANN live in one `WHERE … ORDER BY embedding <=> q` statement inside the same transaction as all other book state.

## Decision

1. Use **PostgreSQL + pgvector** as the only vector store. `vector` columns on `content_chunks`, `concepts`, `notes` (dimensions fixed per deployment by the chosen `EmbeddingProvider`; Phase 1 assumes 1536).
2. ANN index: pgvector HNSW (fallback IVFFlat if operational issues arise), queried with equality filters on scope columns.
3. Embeddings are **content-addressed**: `content_hash` = SHA-256 of normalized text; embedding step skips chunks whose hash already has an embedding with the current `embedding_model` (README §38).
4. `EmbeddingProvider` is an interface; provider/model changes require a migration + re-embed job — never a silent mixed-vector table (`embedding_model` column tracks provenance).
5. A dedicated vector DB may be revisited only when a concrete, measured limitation appears (scale, latency, or a filtering pattern pgvector cannot express). Not before.

## Consequences

- One datastore to back up, migrate, and transact over; consistency between chunks and vectors is transactional.
- ANN performance ceiling is lower than specialized engines; irrelevant at single-workspace / few-hundred-books scale.
- Changing embedding model is an explicit, tracked operation (re-embed job), not an accident.
