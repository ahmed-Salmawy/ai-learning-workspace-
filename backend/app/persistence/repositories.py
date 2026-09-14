import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.persistence.models import (
    Book,
    BookSource,
    BookStatus,
    Chapter,
    ChapterSource,
    ContentChunk,
    Workspace,
)


class WorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, workspace_id: uuid.UUID) -> Workspace | None:
        return self._session.get(Workspace, workspace_id)


class BookRepository:
    def __init__(self, session: Session, workspace_id: uuid.UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    def create(self, *, title: str, author: str | None = None) -> Book:
        book = Book(
            workspace_id=self._workspace_id,
            title=title,
            author=author,
            status=BookStatus.UPLOADED,
        )
        self._session.add(book)
        self._session.flush()
        return book

    def get_scoped(self, book_id: uuid.UUID) -> Book | None:
        stmt = select(Book).where(Book.id == book_id, Book.workspace_id == self._workspace_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def list(self) -> Sequence[Book]:
        stmt = (
            select(Book)
            .where(Book.workspace_id == self._workspace_id)
            .order_by(Book.created_at)
        )
        return self._session.execute(stmt).scalars().all()

    def set_status(self, book_id: uuid.UUID, status: str) -> None:
        book = self.get_scoped(book_id)
        if book is None:
            raise LookupError(f"book {book_id} not found in workspace {self._workspace_id}")
        book.status = status
        if status == BookStatus.READY:
            book.ingested_at = datetime.now(UTC)
        if status != BookStatus.FAILED:
            book.error = None
        self._session.flush()

    def set_failed(self, book_id: uuid.UUID, stage: str, message: str) -> None:
        book = self.get_scoped(book_id)
        if book is None:
            raise LookupError(f"book {book_id} not found in workspace {self._workspace_id}")
        book.status = BookStatus.FAILED
        book.error = {"stage": stage, "message": message}
        self._session.flush()

    def set_metadata(self, book_id: uuid.UUID, *, title: str, author: str | None) -> None:
        book = self.get_scoped(book_id)
        if book is None:
            raise LookupError(f"book {book_id} not found in workspace {self._workspace_id}")
        book.title = title
        book.author = author
        self._session.flush()


class BookSourceRepository:
    def __init__(self, session: Session, workspace_id: uuid.UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    def find_by_file_hash(self, file_hash: str) -> BookSource | None:
        stmt = select(BookSource).where(
            BookSource.workspace_id == self._workspace_id,
            BookSource.file_hash == file_hash,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def find_by_book(self, book_id: uuid.UUID) -> BookSource | None:
        stmt = select(BookSource).where(
            BookSource.workspace_id == self._workspace_id,
            BookSource.book_id == book_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        book_id: uuid.UUID,
        storage_key: str,
        original_filename: str,
        mime_type: str | None,
        file_hash: str,
        page_count: int | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> BookSource:
        source = BookSource(
            workspace_id=self._workspace_id,
            book_id=book_id,
            storage_key=storage_key,
            original_filename=original_filename,
            mime_type=mime_type,
            file_hash=file_hash,
            page_count=page_count,
            source_metadata=source_metadata,
        )
        self._session.add(source)
        self._session.flush()
        return source

    def set_page_count(
        self, book_id: uuid.UUID, page_count: int, source_metadata: dict[str, Any]
    ) -> None:
        stmt = select(BookSource).where(
            BookSource.workspace_id == self._workspace_id, BookSource.book_id == book_id
        )
        source = self._session.execute(stmt).scalar_one_or_none()
        if source is not None:
            source.page_count = page_count
            source.source_metadata = source_metadata
            self._session.flush()


class ChapterRepository:
    def __init__(self, session: Session, workspace_id: uuid.UUID, book_id: uuid.UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id
        self._book_id = book_id

    def replace_all(self, chapters: Sequence[dict[str, Any]]) -> Sequence[Chapter]:
        self.delete_all()
        created = [
            Chapter(
                workspace_id=self._workspace_id,
                book_id=self._book_id,
                ordinal=int(entry["ordinal"]),
                title=str(entry["title"]),
                page_start=entry.get("page_start"),
                page_end=entry.get("page_end"),
                source=entry.get("source", ChapterSource.INFERRED),
            )
            for entry in chapters
        ]
        self._session.add_all(created)
        self._session.flush()
        return created

    def delete_all(self) -> None:
        stmt = select(Chapter).where(
            Chapter.workspace_id == self._workspace_id, Chapter.book_id == self._book_id
        )
        for chapter in self._session.execute(stmt).scalars():
            self._session.delete(chapter)
        self._session.flush()

    def list(self) -> Sequence[Chapter]:
        stmt = (
            select(Chapter)
            .where(
                Chapter.workspace_id == self._workspace_id, Chapter.book_id == self._book_id
            )
            .order_by(Chapter.ordinal)
        )
        return self._session.execute(stmt).scalars().all()


class ChunkRepository:
    def __init__(self, session: Session, workspace_id: uuid.UUID, book_id: uuid.UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id
        self._book_id = book_id

    def existing_hashes(self) -> set[str]:
        stmt = select(ContentChunk.content_hash).where(
            ContentChunk.workspace_id == self._workspace_id,
            ContentChunk.book_id == self._book_id,
        )
        return set(self._session.execute(stmt).scalars())

    def insert_new(
        self, drafts: Sequence[dict[str, Any]], *, start_ordinal: int = 0
    ) -> tuple[int, int]:
        known = self.existing_hashes()
        inserted = 0
        skipped = 0
        ordinal = start_ordinal
        for draft in drafts:
            content_hash = str(draft["content_hash"])
            if content_hash in known:
                skipped += 1
                continue
            known.add(content_hash)
            self._session.add(
                ContentChunk(
                    workspace_id=self._workspace_id,
                    book_id=self._book_id,
                    chapter_id=draft["chapter_id"],
                    ordinal=ordinal,
                    text=draft["text"],
                    section=draft.get("section"),
                    page_start=draft.get("page_start"),
                    page_end=draft.get("page_end"),
                    content_hash=content_hash,
                )
            )
            ordinal += 1
            inserted += 1
        self._session.flush()
        return inserted, skipped

    def count(self) -> int:
        stmt = select(ContentChunk.id).where(
            ContentChunk.workspace_id == self._workspace_id,
            ContentChunk.book_id == self._book_id,
        )
        return len(self._session.execute(stmt).scalars().all())

    def all_ordered(self) -> Sequence[ContentChunk]:
        stmt = (
            select(ContentChunk)
            .where(
                ContentChunk.workspace_id == self._workspace_id,
                ContentChunk.book_id == self._book_id,
            )
            .order_by(ContentChunk.ordinal)
        )
        return self._session.execute(stmt).scalars().all()

    def chunks_without_embedding(self, embedding_model: str) -> Sequence[ContentChunk]:
        stmt = (
            select(ContentChunk)
            .where(
                ContentChunk.workspace_id == self._workspace_id,
                ContentChunk.book_id == self._book_id,
                ContentChunk.embedding.is_(None)
                | (ContentChunk.embedding_model != embedding_model),
            )
            .order_by(ContentChunk.ordinal)
        )
        return self._session.execute(stmt).scalars().all()

    def set_embedding(self, chunk_id: uuid.UUID, vector: list[float], model: str) -> None:
        stmt = (
            update(ContentChunk)
            .where(
                ContentChunk.id == chunk_id,
                ContentChunk.workspace_id == self._workspace_id,
                ContentChunk.book_id == self._book_id,
            )
            .values(embedding=vector, embedding_model=model)
        )
        self._session.execute(stmt)
        self._session.flush()
