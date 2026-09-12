"""conversations and messages

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-11

Per docs/DOMAIN_MODEL.md §2.6: Ask-the-Book conversations + messages with
citation payloads and knowledge-source separation (README §6/§21).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=32)


def upgrade() -> None:
    op.create_table(
        "conversations",
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
            "kind",
            _enum(
                "conversation_kind",
                "ASK_BOOK",
                "TUTOR",
                "DEBUG_MY_UNDERSTANDING",
            ),
            nullable=False,
        ),
        sa.Column(
            "tutor_mode",
            _enum(
                "tutor_mode",
                "TEACH",
                "SOCRATIC",
                "TEST",
                "INTERVIEW",
                "RECALL",
                "EXPLAIN",
            ),
            nullable=True,
        ),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_conversations_workspace_id", "conversations", ["workspace_id"])
    op.create_index("ix_conversations_book_id", "conversations", ["book_id"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role", _enum("message_role", "USER", "ASSISTANT", "SYSTEM"), nullable=False
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB, nullable=True),
        sa.Column(
            "knowledge_source",
            _enum("knowledge_source", "BOOK", "LEARNER", "SYSTEM"),
            nullable=False,
        ),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_workspace_id", "messages", ["workspace_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    for enum_name in (
        "knowledge_source",
        "message_role",
        "tutor_mode",
        "conversation_kind",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
