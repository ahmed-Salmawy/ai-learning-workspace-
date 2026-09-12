import logging
from uuid import UUID

from sqlalchemy.orm import sessionmaker

from app.llm.protocols import EmbeddingProvider, LLMProvider
from app.llm.structured import structured_call
from app.orchestration.ask_schemas import (
    ASK_SYSTEM_PROMPT,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    AskLLMResponse,
    AskResult,
    CitationOut,
)
from app.persistence.conversation_models import (
    Conversation,
    ConversationKind,
    KnowledgeSource,
    Message,
    MessageRole,
)
from app.persistence.models import BookStatus
from app.persistence.repositories import BookRepository, ChapterRepository
from app.retrieval.protocols import RetrievalEngine, RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 8
ASK_BOOK_KIND = ConversationKind.ASK_BOOK


class BookNotReadyError(RuntimeError):
    pass


def _canonical_chunk_id(chunk_id: str) -> str | None:
    try:
        return str(UUID(chunk_id))
    except (ValueError, AttributeError, TypeError):
        return None


def intersect_citations(
    claimed_chunk_ids: list[str], retrieved: list[RetrievedChunk]
) -> list[RetrievedChunk]:
    by_id = {str(chunk.chunk_id): chunk for chunk in retrieved}
    seen: set[str] = set()
    kept: list[RetrievedChunk] = []
    for chunk_id in claimed_chunk_ids:
        canonical = _canonical_chunk_id(chunk_id)
        if canonical is None or canonical in seen:
            continue
        chunk = by_id.get(canonical)
        if chunk is not None:
            seen.add(canonical)
            kept.append(chunk)
    return kept


class AskService:
    def __init__(
        self,
        session_factory: sessionmaker,
        *,
        embeddings: EmbeddingProvider,
        retrieval: RetrievalEngine,
        llm: LLMProvider,
        model: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embeddings = embeddings
        self._retrieval = retrieval
        self._llm = llm
        self._model = model

    def ask(
        self,
        workspace_id: UUID,
        book_id: UUID,
        question: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> AskResult:
        with self._session_factory() as session:
            book = BookRepository(session, workspace_id).get_scoped(book_id)
            if book is None:
                raise LookupError(f"book {book_id} not found")
            if book.status != BookStatus.READY:
                raise BookNotReadyError(
                    f"book {book_id} is not READY (status={book.status})"
                )
            title = book.title

        query_embedding = self._embeddings.embed([question])[0]
        retrieved = self._retrieval.search(
            workspace_id=workspace_id,
            book_id=book_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        with self._session_factory() as session:
            chapter_ordinals = {
                chapter.id: chapter.ordinal
                for chapter in ChapterRepository(session, workspace_id, book_id).list()
            }

        response = structured_call(
            self._llm,
            ASK_SYSTEM_PROMPT,
            _user_prompt(title, question, retrieved),
            AskLLMResponse,
            model=self._model,
        )

        cited = intersect_citations(
            [citation.chunk_id for citation in response.citations], retrieved
        )
        insufficient = response.insufficient_evidence or not cited or not response.book_grounded

        if insufficient:
            answer = INSUFFICIENT_EVIDENCE_MESSAGE
            citations: list[CitationOut] = []
            book_grounded = False
        else:
            answer = response.answer
            citations = [_citation_from_chunk(chunk, book_id, chapter_ordinals) for chunk in cited]
            book_grounded = True

        conversation_id = self._persist(
            workspace_id,
            book_id,
            question,
            answer,
            [citation.model_dump(by_alias=True) for citation in citations],
            response.general_knowledge_note if not insufficient else None,
        )

        return AskResult.model_validate(
            {
                "answer": answer,
                "book_grounded": book_grounded,
                "citations": [citation.model_dump() for citation in citations],
                "insufficient_evidence": insufficient,
                "general_knowledge_note": response.general_knowledge_note,
                "conversation_id": str(conversation_id),
            }
        )

    def _persist(
        self,
        workspace_id: UUID,
        book_id: UUID,
        question: str,
        answer: str,
        citations: list[dict],
        general_note: str | None,
    ) -> UUID:
        with self._session_factory() as session:
            conversation = Conversation(
                workspace_id=workspace_id,
                book_id=book_id,
                kind=ASK_BOOK_KIND,
            )
            session.add(conversation)
            session.flush()
            session.add(
                Message(
                    workspace_id=workspace_id,
                    conversation_id=conversation.id,
                    role=MessageRole.USER,
                    content=question,
                    knowledge_source=KnowledgeSource.LEARNER,
                )
            )
            session.add(
                Message(
                    workspace_id=workspace_id,
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=answer,
                    citations=citations,
                    knowledge_source=KnowledgeSource.BOOK,
                )
            )
            if general_note:
                session.add(
                    Message(
                        workspace_id=workspace_id,
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=general_note,
                        knowledge_source=KnowledgeSource.SYSTEM,
                    )
                )
            session.commit()
            return conversation.id


def _citation_from_chunk(
    chunk: RetrievedChunk, book_id: UUID, chapter_ordinals: dict[UUID, int]
) -> CitationOut:
    return CitationOut.model_validate(
        {
            "chunk_id": str(chunk.chunk_id),
            "book_id": str(book_id),
            "chapter": chapter_ordinals.get(chunk.chapter_id) if chunk.chapter_id else None,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "section": chunk.section,
        }
    )


def _user_prompt(title: str, question: str, retrieved: list[RetrievedChunk]) -> str:
    passages = "\n\n".join(
        f"[passage_id: {chunk.chunk_id}]\n{chunk.text}" for chunk in retrieved
    )
    return (
        f'Book: "{title}"\n\n'
        f"Passages retrieved from the book:\n\n{passages}\n\n"
        f"Question: {question}"
    )
