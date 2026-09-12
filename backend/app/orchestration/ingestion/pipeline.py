import functools
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.metrics import METRICS
from app.engines.llm_roadmap import normalize_name
from app.engines.protocols import RoadmapEngine
from app.llm.protocols import EmbeddingProvider
from app.orchestration.ingestion.chunking import ChunkDraft, chunk_document
from app.orchestration.ingestion.extract import ExtractedDocument, TextExtractor
from app.orchestration.ingestion.extractors import PlainTextExtractor, PyMuPDFTextExtractor
from app.orchestration.ingestion.toc import DetectedChapter, detect_toc
from app.persistence.concept_repositories import (
    ConceptRelationshipRepository,
    ConceptRepository,
)
from app.persistence.models import BookStatus, ChapterSource
from app.persistence.repositories import (
    BookRepository,
    BookSourceRepository,
    ChapterRepository,
    ChunkRepository,
)
from app.storage.protocols import ObjectStorage

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 64

STAGE_PARSE = "parse"
STAGE_CHUNK = "chunk"
STAGE_EMBED = "embed"
STAGE_EXTRACT = "extract"


@dataclass(frozen=True)
class StageResult:
    stage: str
    book_id: UUID
    from_status: str
    to_status: str


class BookNotFoundError(LookupError):
    pass


def _instrumented(stage: str) -> Any:
    def decorate(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(self: Any, workspace_id: Any, book_id: Any, from_status: Any) -> Any:
            start = time.perf_counter()
            try:
                result = fn(self, workspace_id, book_id, from_status)
            except Exception:
                METRICS.increment("ingestion_stage_total", stage=stage, status="error")
                METRICS.observe(
                    "ingestion_stage_seconds",
                    time.perf_counter() - start,
                    stage=stage,
                )
                raise
            METRICS.increment("ingestion_stage_total", stage=stage, status="ok")
            METRICS.observe(
                "ingestion_stage_seconds", time.perf_counter() - start, stage=stage
            )
            return result

        return wrapper

    return decorate


class IngestionPipeline:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: ObjectStorage,
        extractor: TextExtractor | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        roadmap_engine: RoadmapEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._extractor = extractor
        self._embedding_provider = embedding_provider
        self._roadmap_engine = roadmap_engine

    def advance(self, workspace_id: UUID, book_id: UUID) -> StageResult:
        with self._session_factory() as session:
            books = BookRepository(session, workspace_id)
            book = books.get_scoped(book_id)
            if book is None:
                raise BookNotFoundError(f"book {book_id} not found")
            status = book.status
            failed_stage: str | None = None
            if book.error and isinstance(book.error, dict):
                failed_stage = book.error.get("stage")
            book_id_str: UUID = book.id

        if status == BookStatus.UPLOADED or (
            status == BookStatus.FAILED and failed_stage == STAGE_PARSE
        ):
            return self._run_parse_stage(workspace_id, book_id_str, status)
        if status == BookStatus.PARSING or (
            status == BookStatus.FAILED and failed_stage == STAGE_CHUNK
        ):
            return self._run_chunk_stage(workspace_id, book_id_str, status)
        if (
            self._embedding_provider is not None
            and status == BookStatus.CHUNKED
            or (
                self._embedding_provider is not None
                and status == BookStatus.FAILED
                and failed_stage == STAGE_EMBED
            )
        ):
            return self._run_embed_stage(workspace_id, book_id_str, status)
        if (
            self._roadmap_engine is not None and status == BookStatus.EMBEDDED
        ) or (
            self._roadmap_engine is not None
            and status == BookStatus.FAILED
            and failed_stage == STAGE_EXTRACT
        ):
            return self._run_extract_stage(workspace_id, book_id_str, status)
        if self._embedding_provider is not None and status == BookStatus.EMBEDDED:
            return self._run_embed_stage(workspace_id, book_id_str, status)
        return StageResult(stage="noop", book_id=book_id, from_status=status, to_status=status)

    def run_to_completion(self, workspace_id: UUID, book_id: UUID) -> list[StageResult]:
        results: list[StageResult] = []
        for _ in range(10):
            result = self.advance(workspace_id, book_id)
            if result.stage == "noop" or result.to_status == result.from_status:
                break
            results.append(result)
        return results

    @_instrumented('parse')
    def _run_parse_stage(self, workspace_id: UUID, book_id: UUID, from_status: str) -> StageResult:
        try:
            with self._session_factory() as session:
                books = BookRepository(session, workspace_id)
                sources = BookSourceRepository(session, workspace_id)
                book = books.get_scoped(book_id)
                if book is None:
                    raise BookNotFoundError(f"book {book_id} not found")
                source = sources.find_by_book(book_id)
                if source is None:
                    raise BookNotFoundError(f"book source for {book_id} not found")
                data = self._storage.get(source.storage_key)
                extractor = self._extractor or _extractor_for(
                    source.mime_type, source.original_filename
                )
                document = extractor.extract(data)
                detection = detect_toc(document)
                chapters = _with_front_matter(detection.chapters, _page_count(document))
                chapter_repo = ChapterRepository(session, workspace_id, book_id)
                chapter_repo.replace_all(
                    [
                        {
                            "ordinal": chapter.ordinal,
                            "title": chapter.title,
                            "page_start": chapter.page_start,
                            "page_end": chapter.page_end,
                            "source": (
                                ChapterSource.TOC
                                if chapter.source == "TOC"
                                else ChapterSource.INFERRED
                            ),
                        }
                        for chapter in chapters
                    ]
                )
                books.set_metadata(
                    book_id, title=document.title or book.title, author=document.author
                )
                sources.set_page_count(
                    book_id,
                    _page_count(document),
                    {
                        "toc_source": detection.source,
                        "toc_confidence": detection.confidence,
                        "chapters_detected": len(chapters),
                    },
                )
                books.set_status(book_id, BookStatus.PARSING)
                session.commit()
        except Exception as exc:
            self._mark_failed(workspace_id, book_id, STAGE_PARSE, exc)
            raise
        logger.info(
            "ingestion parse stage complete",
            extra={
                "workspace_id": str(workspace_id),
                "book_id": str(book_id),
                "stage": STAGE_PARSE,
            },
        )
        return StageResult(
            stage=STAGE_PARSE,
            book_id=book_id,
            from_status=from_status,
            to_status=BookStatus.PARSING,
        )

    @_instrumented('chunk')
    def _run_chunk_stage(self, workspace_id: UUID, book_id: UUID, from_status: str) -> StageResult:
        try:
            with self._session_factory() as session:
                books = BookRepository(session, workspace_id)
                sources = BookSourceRepository(session, workspace_id)
                chapter_repo = ChapterRepository(session, workspace_id, book_id)
                chunk_repo = ChunkRepository(session, workspace_id, book_id)

                book = books.get_scoped(book_id)
                if book is None:
                    raise BookNotFoundError(f"book {book_id} not found")
                source = sources.find_by_book(book_id)
                if source is None:
                    raise BookNotFoundError(f"book source for {book_id} not found")
                chapters = [
                    DetectedChapter(
                        ordinal=chapter.ordinal,
                        title=chapter.title,
                        page_start=chapter.page_start or 1,
                        page_end=chapter.page_end,
                        source=chapter.source,
                        confidence=0.9 if chapter.source == ChapterSource.TOC else 0.5,
                    )
                    for chapter in chapter_repo.list()
                ]
                if not chapters:
                    raise ValueError(f"no chapters for book {book_id}; rerun parse stage")

                document = self._load_document(source.storage_key)
                drafts = chunk_document(document, chapters)
                chapter_rows = {chapter.ordinal: chapter for chapter in chapter_repo.list()}
                valid_drafts = [
                    _draft_with_chapter_id(draft, chapter_rows) for draft in drafts
                ]
                inserted, skipped = chunk_repo.insert_new(valid_drafts)
                METRICS.increment("ingestion_chunks_inserted_total", value=inserted)
                books.set_status(book_id, BookStatus.CHUNKED)
                session.commit()
        except Exception as exc:
            self._mark_failed(workspace_id, book_id, STAGE_CHUNK, exc)
            raise
        logger.info(
            "ingestion chunk stage complete",
            extra={
                "workspace_id": str(workspace_id),
                "book_id": str(book_id),
                "stage": STAGE_CHUNK,
                "inserted": inserted,
                "skipped": skipped,
            },
        )
        return StageResult(
            stage=STAGE_CHUNK,
            book_id=book_id,
            from_status=from_status,
            to_status=BookStatus.CHUNKED,
        )

    def _load_document(self, storage_key: str) -> ExtractedDocument:
        data = self._storage.get(storage_key)
        return (self._extractor or PyMuPDFTextExtractor()).extract(data)

    def _mark_failed(self, workspace_id: UUID, book_id: UUID, stage: str, exc: Exception) -> None:
        try:
            with self._session_factory() as session:
                BookRepository(session, workspace_id).set_failed(book_id, stage, str(exc))
                session.commit()
        except Exception:
            logger.exception("failed to mark book %s as FAILED", book_id)

    @_instrumented('embed')
    def _run_embed_stage(self, workspace_id: UUID, book_id: UUID, from_status: str) -> StageResult:
        if self._embedding_provider is None:
            raise RuntimeError(
                "embedding provider not configured (set ALW_EMBEDDING_MODEL / ALW_OPENAI_*)"
            )
        try:
            provider = self._embedding_provider
            with self._session_factory() as session:
                books = BookRepository(session, workspace_id)
                chunk_repo = ChunkRepository(session, workspace_id, book_id)
                book = books.get_scoped(book_id)
                if book is None:
                    raise BookNotFoundError(f"book {book_id} not found")

                pending = chunk_repo.chunks_without_embedding(provider.model)
                embedded = 0
                for batch_start in range(0, len(pending), EMBED_BATCH_SIZE):
                    batch = pending[batch_start : batch_start + EMBED_BATCH_SIZE]
                    with METRICS.timer("embedding_seconds"):
                        vectors = provider.embed([chunk.text for chunk in batch])
                    for chunk, vector in zip(batch, vectors, strict=True):
                        chunk_repo.set_embedding(chunk.id, vector, provider.model)
                        embedded += 1
                books.set_status(book_id, BookStatus.EMBEDDED)
                session.commit()
        except Exception as exc:
            self._mark_failed(workspace_id, book_id, STAGE_EMBED, exc)
            raise
        logger.info(
            "ingestion embed stage complete",
            extra={
                "workspace_id": str(workspace_id),
                "book_id": str(book_id),
                "stage": STAGE_EMBED,
                "embedded": embedded,
            },
        )
        return StageResult(
            stage=STAGE_EMBED,
            book_id=book_id,
            from_status=from_status,
            to_status=BookStatus.EMBEDDED,
        )

    @_instrumented('extract')
    def _run_extract_stage(
        self, workspace_id: UUID, book_id: UUID, from_status: str
    ) -> StageResult:
        engine = self._roadmap_engine
        if engine is None:
            raise RuntimeError("roadmap engine not configured")
        try:
            with self._session_factory() as session:
                books = BookRepository(session, workspace_id)
                book = books.get_scoped(book_id)
                if book is None:
                    raise BookNotFoundError(f"book {book_id} not found")

                chunk_repo = ChunkRepository(session, workspace_id, book_id)
                concept_repo = ConceptRepository(session, workspace_id, book_id)
                relationship_repo = ConceptRelationshipRepository(
                    session, workspace_id, book_id
                )

                chunk_texts = [chunk.text for chunk in chunk_repo.all_ordered()]
                extracted = engine.extract_concepts(
                    workspace_id=workspace_id, book_id=book_id, chunk_texts=chunk_texts
                )
                concepts_inserted, concepts_skipped = concept_repo.insert_new(
                    [
                        {
                            "name": concept.name,
                            "normalized_name": concept.normalized_name,
                            "description": concept.description,
                        }
                        for concept in extracted
                    ]
                )
                concepts_by_name = concept_repo.by_normalized_name()
                dependencies = engine.build_dependencies(
                    workspace_id=workspace_id, book_id=book_id, concepts=extracted
                )
                edges_inserted, edges_skipped = relationship_repo.insert_new(
                    [
                        {
                            "from_concept": normalize_name(relationship.from_concept),
                            "to_concept": normalize_name(relationship.to_concept),
                            "relation": relationship.relation,
                            "confidence": relationship.confidence,
                        }
                        for relationship in dependencies
                    ],
                    concepts_by_name,
                )
                books.set_status(book_id, BookStatus.READY)
                session.commit()
        except Exception as exc:
            self._mark_failed(workspace_id, book_id, STAGE_EXTRACT, exc)
            raise
        logger.info(
            "ingestion extract stage complete",
            extra={
                "workspace_id": str(workspace_id),
                "book_id": str(book_id),
                "stage": STAGE_EXTRACT,
                "concepts_inserted": concepts_inserted,
                "concepts_skipped": concepts_skipped,
                "edges_inserted": edges_inserted,
                "edges_skipped": edges_skipped,
            },
        )
        return StageResult(
            stage=STAGE_EXTRACT,
            book_id=book_id,
            from_status=from_status,
            to_status=BookStatus.READY,
        )


def _draft_with_chapter_id(draft: ChunkDraft, chapters: dict[int, Any]) -> dict[str, Any]:
    chapter = chapters.get(draft.chapter_ordinal)
    if chapter is None:
        raise ValueError(f"chunk references missing chapter ordinal {draft.chapter_ordinal}")
    return {
        "chapter_id": chapter.id,
        "text": draft.text,
        "section": draft.section,
        "page_start": draft.page_start,
        "page_end": draft.page_end,
        "content_hash": draft.content_hash,
    }


def _with_front_matter(
    chapters: list[DetectedChapter], total_pages: int
) -> list[DetectedChapter]:
    if not chapters:
        return [
            DetectedChapter(
                ordinal=1, title="Full text", page_start=1, page_end=total_pages,
                source="INFERRED", confidence=0.3,
            )
        ]
    first = min(chapters, key=lambda c: c.page_start)
    if first.page_start <= 1:
        return chapters
    front = DetectedChapter(
        ordinal=0,
        title="Front matter",
        page_start=1,
        page_end=first.page_start - 1,
        source="INFERRED",
        confidence=0.4,
    )
    return [front] + chapters


def _page_count(document: ExtractedDocument) -> int:
    return max((page.ordinal for page in document.pages), default=0)


def _extractor_for(mime_type: str | None, filename: str) -> TextExtractor:
    name = filename.lower()
    if (mime_type and "pdf" in mime_type) or name.endswith(".pdf"):
        return PyMuPDFTextExtractor()
    return PlainTextExtractor()
