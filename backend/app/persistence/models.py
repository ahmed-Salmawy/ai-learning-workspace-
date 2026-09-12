import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSION = 1536


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IsolationMixin:
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class BookStatus:
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    CHUNKED = "CHUNKED"
    EMBEDDED = "EMBEDDED"
    READY = "READY"
    FAILED = "FAILED"


book_status_enum = Enum(
    BookStatus.UPLOADED,
    BookStatus.PARSING,
    BookStatus.CHUNKED,
    BookStatus.EMBEDDED,
    BookStatus.READY,
    BookStatus.FAILED,
    name="book_status",
    native_enum=False,
    length=32,
)


class Book(Base, TimestampMixin, IsolationMixin):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(book_status_enum, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_books_workspace_status", "workspace_id", "status"),)


class BookSource(Base, TimestampMixin, IsolationMixin):
    __tablename__ = "book_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)

    __table_args__ = (
        UniqueConstraint("workspace_id", "file_hash", name="uq_book_sources_ws_file_hash"),
    )


class ChapterSource:
    TOC = "TOC"
    INFERRED = "INFERRED"


chapter_source_enum = Enum(
    ChapterSource.TOC,
    ChapterSource.INFERRED,
    name="chapter_source",
    native_enum=False,
    length=32,
)


class Chapter(Base, TimestampMixin, IsolationMixin):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(chapter_source_enum, nullable=False)

    __table_args__ = (
        UniqueConstraint("book_id", "ordinal", name="uq_chapters_book_ordinal"),
    )


class ContentChunk(Base, TimestampMixin, IsolationMixin):
    __tablename__ = "content_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(String(512))
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    token_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("book_id", "content_hash", name="uq_content_chunks_book_hash"),
        Index("ix_content_chunks_book_ordinal", "book_id", "ordinal"),
        Index(
            "ix_content_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Concept(Base, TimestampMixin, IsolationMixin):
    __tablename__ = "concepts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))

    __table_args__ = (
        UniqueConstraint("book_id", "normalized_name", name="uq_concepts_book_norm_name"),
    )


class LearningEventType:
    BOOK_OPENED = "BOOK_OPENED"
    CHAPTER_STARTED = "CHAPTER_STARTED"
    CHAPTER_COMPLETED = "CHAPTER_COMPLETED"
    CHUNK_READ = "CHUNK_READ"
    QUESTION_ASKED = "QUESTION_ASKED"
    ANSWER_GIVEN = "ANSWER_GIVEN"
    ASSESSMENT_COMPLETED = "ASSESSMENT_COMPLETED"
    RECALL_COMPLETED = "RECALL_COMPLETED"
    MASTERY_CHANGED = "MASTERY_CHANGED"


learning_event_type_enum = Enum(
    LearningEventType.BOOK_OPENED,
    LearningEventType.CHAPTER_STARTED,
    LearningEventType.CHAPTER_COMPLETED,
    LearningEventType.CHUNK_READ,
    LearningEventType.QUESTION_ASKED,
    LearningEventType.ANSWER_GIVEN,
    LearningEventType.ASSESSMENT_COMPLETED,
    LearningEventType.RECALL_COMPLETED,
    LearningEventType.MASTERY_CHANGED,
    name="learning_event_type",
    native_enum=False,
    length=32,
)


class LearningEvent(Base, TimestampMixin, IsolationMixin):
    __tablename__ = "learning_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="SET NULL"), index=True
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(learning_event_type_enum, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_learning_events_occurred_at_brin", "occurred_at", postgresql_using="brin"),
    )


class RelationType:
    PREREQUISITE_OF = "PREREQUISITE_OF"
    RELATED_TO = "RELATED_TO"
    CONTRASTS_WITH = "CONTRASTS_WITH"
    IMPLEMENTED_BY = "IMPLEMENTED_BY"
    CAUSES = "CAUSES"
    PREVENTS = "PREVENTS"
    EXAMPLE_OF = "EXAMPLE_OF"
    PART_OF = "PART_OF"


concept_relation_enum = Enum(
    RelationType.PREREQUISITE_OF,
    RelationType.RELATED_TO,
    RelationType.CONTRASTS_WITH,
    RelationType.IMPLEMENTED_BY,
    RelationType.CAUSES,
    RelationType.PREVENTS,
    RelationType.EXAMPLE_OF,
    RelationType.PART_OF,
    name="concept_relation",
    native_enum=False,
    length=32,
)

relationship_source_enum = Enum(
    "LLM",
    "MANUAL",
    name="relationship_source",
    native_enum=False,
    length=32,
)


class ConceptRelationship(Base):
    __tablename__ = "concept_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation: Mapped[str] = mapped_column(concept_relation_enum, nullable=False)
    source: Mapped[str] = mapped_column(relationship_source_enum, nullable=False)
    confidence: Mapped[float | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "from_concept_id",
            "to_concept_id",
            "relation",
            name="uq_concept_relationships_edge",
        ),
    )
