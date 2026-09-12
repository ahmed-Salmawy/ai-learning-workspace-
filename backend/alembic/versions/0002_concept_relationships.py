"""concept relationships

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-11

Per docs/DOMAIN_MODEL.md §2.2: edges within a book, stored in Phase 1
(buildDependencies), consumed in Phase 2.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, length=32)


def upgrade() -> None:
    op.create_table(
        "concept_relationships",
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
            "from_concept_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_concept_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relation",
            _enum(
                "concept_relation",
                "PREREQUISITE_OF",
                "RELATED_TO",
                "CONTRASTS_WITH",
                "IMPLEMENTED_BY",
                "CAUSES",
                "PREVENTS",
                "EXAMPLE_OF",
                "PART_OF",
            ),
            nullable=False,
        ),
        sa.Column("source", _enum("relationship_source", "LLM", "MANUAL"), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "book_id",
            "from_concept_id",
            "to_concept_id",
            "relation",
            name="uq_concept_relationships_edge",
        ),
    )
    op.create_index(
        "ix_concept_relationships_workspace_id",
        "concept_relationships",
        ["workspace_id"],
    )
    op.create_index("ix_concept_relationships_book_id", "concept_relationships", ["book_id"])
    op.create_index(
        "ix_concept_relationships_from_concept", "concept_relationships", ["from_concept_id"]
    )
    op.create_index(
        "ix_concept_relationships_to_concept", "concept_relationships", ["to_concept_id"]
    )


def downgrade() -> None:
    op.drop_table("concept_relationships")
    sa.Enum(name="relationship_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="concept_relation").drop(op.get_bind(), checkfirst=True)
