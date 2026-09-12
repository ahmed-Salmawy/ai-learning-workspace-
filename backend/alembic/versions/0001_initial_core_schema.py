"""initial core schema

Revision ID: 0001
Revises:
Create Date: 2026-09-11

Core Phase 1 subset per docs/DOMAIN_MODEL.md:
users, workspaces, books, book_sources, chapters, content_chunks,
concepts (+ pgvector embedding), learning_events.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSION = 1536

TS = sa.DateTime(timezone=True)
JSONB = postgresql.JSONB


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
    ]


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=32)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"])

    op.create_table(
        "books",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author", sa.String(512), nullable=True),
        sa.Column(
            "status",
            _enum("book_status", "UPLOADED", "PARSING", "CHUNKED", "EMBEDDED", "READY", "FAILED"),
            nullable=False,
        ),
        sa.Column("error", JSONB, nullable=True),
        sa.Column("ingested_at", TS, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_books_workspace_id", "books", ["workspace_id"])
    op.create_index("ix_books_workspace_status", "books", ["workspace_id", "status"])

    op.create_table(
        "book_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "file_hash", name="uq_book_sources_ws_file_hash"),
    )
    op.create_index("ix_book_sources_workspace_id", "book_sources", ["workspace_id"])
    op.create_index("ix_book_sources_book_id", "book_sources", ["book_id"])

    op.create_table(
        "chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("source", _enum("chapter_source", "TOC", "INFERRED"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("book_id", "ordinal", name="uq_chapters_book_ordinal"),
    )
    op.create_index("ix_chapters_workspace_id", "chapters", ["workspace_id"])
    op.create_index("ix_chapters_book_id", "chapters", ["book_id"])

    op.create_table(
        "content_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("section", sa.String(512), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
        sa.Column("embedding_model", sa.String(255), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("book_id", "content_hash", name="uq_content_chunks_book_hash"),
    )
    op.create_index("ix_content_chunks_workspace_id", "content_chunks", ["workspace_id"])
    op.create_index("ix_content_chunks_book_id", "content_chunks", ["book_id"])
    op.create_index("ix_content_chunks_book_ordinal", "content_chunks", ["book_id", "ordinal"])
    op.create_index(
        "ix_content_chunks_embedding_hnsw",
        "content_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "concepts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("normalized_name", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("book_id", "normalized_name", name="uq_concepts_book_norm_name"),
    )
    op.create_index("ix_concepts_workspace_id", "concepts", ["workspace_id"])
    op.create_index("ix_concepts_book_id", "concepts", ["book_id"])

    op.create_table(
        "learning_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "concept_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "event_type",
            _enum("learning_event_type", "BOOK_OPENED", "CHAPTER_STARTED", "CHAPTER_COMPLETED",
                  "CHUNK_READ", "QUESTION_ASKED", "ANSWER_GIVEN", "ASSESSMENT_COMPLETED",
                  "RECALL_COMPLETED", "MASTERY_CHANGED"),
            nullable=False,
        ),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("occurred_at", TS, nullable=False, server_default=sa.text("now()")),
        *_timestamps(),
    )
    op.create_index("ix_learning_events_workspace_id", "learning_events", ["workspace_id"])
    op.create_index("ix_learning_events_book_id", "learning_events", ["book_id"])
    op.create_index(
        "ix_learning_events_occurred_at_brin",
        "learning_events",
        ["occurred_at"],
        postgresql_using="brin",
    )


def downgrade() -> None:
    op.drop_table("learning_events")
    op.drop_table("concepts")
    op.drop_table("content_chunks")
    op.drop_table("chapters")
    op.drop_table("book_sources")
    op.drop_table("books")
    op.drop_table("workspaces")
    op.drop_table("users")
    sa.Enum(name="learning_event_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="chapter_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="book_status").drop(op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
