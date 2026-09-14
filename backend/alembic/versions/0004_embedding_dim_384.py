"""switch embedding dimension to 384 (local MiniLM)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-11

Deployment-wide embedding dimension change per DOMAIN_MODEL §3.4 / ADR-003:
provider change (OpenAI-compatible 1536 -> local sentence-transformers 384)
requires a migration + re-embed. Existing embeddings are dropped by the
column type change; re-ingest/resume re-embeds (content-addressed skip keys
on embedding_model, which also changes).
"""
from collections.abc import Sequence

from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_DIM = 1536
NEW_DIM = 384


def _upgrade_table(table: str, index: str | None = None) -> None:
    if index:
        op.drop_index(index, table_name=table)
    op.execute(f"UPDATE {table} SET embedding = NULL")
    op.alter_column(
        table,
        "embedding",
        type_=Vector(NEW_DIM),
        postgresql_using="embedding::text::vector",
        existing_nullable=True,
    )
    if index:
        op.create_index(
            index,
            table,
            ["embedding"],
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )


def upgrade() -> None:
    _upgrade_table("content_chunks", "ix_content_chunks_embedding_hnsw")
    _upgrade_table("concepts")


def downgrade() -> None:
    op.alter_column(
        "concepts",
        "embedding",
        type_=Vector(OLD_DIM),
        postgresql_using="USING embedding::text::vector",
        existing_nullable=True,
    )
    op.drop_index("ix_content_chunks_embedding_hnsw", table_name="content_chunks")
    op.execute("UPDATE content_chunks SET embedding = NULL")
    op.alter_column(
        "content_chunks",
        "embedding",
        type_=Vector(OLD_DIM),
        postgresql_using="USING embedding::text::vector",
        existing_nullable=True,
    )
    op.create_index(
        "ix_content_chunks_embedding_hnsw",
        "content_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
