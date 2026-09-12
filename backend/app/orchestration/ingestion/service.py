from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex
from app.persistence.models import BookStatus
from app.persistence.repositories import BookRepository, BookSourceRepository
from app.storage.protocols import ObjectStorage


@dataclass(frozen=True)
class UploadResult:
    book_id: UUID
    created: bool
    status: str


def upload_book(
    session: Session,
    storage: ObjectStorage,
    *,
    workspace_id: UUID,
    filename: str,
    data: bytes,
    mime_type: str | None = None,
) -> UploadResult:
    books = BookRepository(session, workspace_id)
    sources = BookSourceRepository(session, workspace_id)

    file_hash = sha256_hex(data)
    existing = sources.find_by_file_hash(file_hash)
    if existing is not None:
        book = books.get_scoped(existing.book_id)
        if book is not None:
            return UploadResult(book_id=book.id, created=False, status=book.status)

    title = Path(filename).stem.replace("_", " ").strip() or "Untitled"
    book = books.create(title=title)
    key = f"workspaces/{workspace_id}/books/{book.id}/source/{Path(filename).name}"
    storage.put(key=key, data=data, content_type=mime_type)
    sources.create(
        book_id=book.id,
        storage_key=key,
        original_filename=filename,
        mime_type=mime_type,
        file_hash=file_hash,
    )
    return UploadResult(book_id=book.id, created=True, status=BookStatus.UPLOADED)
