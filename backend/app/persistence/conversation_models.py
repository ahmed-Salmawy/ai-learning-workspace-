import uuid
from typing import Any

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models import Base, TimestampMixin


class ConversationKind:
    ASK_BOOK = "ASK_BOOK"
    TUTOR = "TUTOR"
    DEBUG_MY_UNDERSTANDING = "DEBUG_MY_UNDERSTANDING"


conversation_kind_enum = Enum(
    ConversationKind.ASK_BOOK,
    ConversationKind.TUTOR,
    ConversationKind.DEBUG_MY_UNDERSTANDING,
    name="conversation_kind",
    native_enum=False,
    length=32,
)


class TutorMode:
    TEACH = "TEACH"
    SOCRATIC = "SOCRATIC"
    TEST = "TEST"
    INTERVIEW = "INTERVIEW"
    RECALL = "RECALL"
    EXPLAIN = "EXPLAIN"


tutor_mode_enum = Enum(
    TutorMode.TEACH,
    TutorMode.SOCRATIC,
    TutorMode.TEST,
    TutorMode.INTERVIEW,
    TutorMode.RECALL,
    TutorMode.EXPLAIN,
    name="tutor_mode",
    native_enum=False,
    length=32,
)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

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
    kind: Mapped[str] = mapped_column(conversation_kind_enum, nullable=False)
    tutor_mode: Mapped[str | None] = mapped_column(tutor_mode_enum)


class MessageRole:
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


message_role_enum = Enum(
    MessageRole.USER,
    MessageRole.ASSISTANT,
    MessageRole.SYSTEM,
    name="message_role",
    native_enum=False,
    length=32,
)


class KnowledgeSource:
    BOOK = "BOOK"
    LEARNER = "LEARNER"
    SYSTEM = "SYSTEM"


knowledge_source_enum = Enum(
    KnowledgeSource.BOOK,
    KnowledgeSource.LEARNER,
    KnowledgeSource.SYSTEM,
    name="knowledge_source",
    native_enum=False,
    length=32,
)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(message_role_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    knowledge_source: Mapped[str] = mapped_column(knowledge_source_enum, nullable=False)
