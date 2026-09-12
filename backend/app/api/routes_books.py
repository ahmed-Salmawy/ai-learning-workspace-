from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_existing_workspace
from app.orchestration.ingestion.service import upload_book
from app.persistence.db import get_session
from app.persistence.models import Book, Workspace
from app.persistence.repositories import BookRepository, ChapterRepository, ChunkRepository
from app.storage.protocols import ObjectStorage
from app.workers.ingestion import AdvanceJob, get_advance_job, get_storage

router = APIRouter(prefix="/workspaces/{workspace_id}/books", tags=["books"])


def _book_payload(book: Book) -> dict[str, object]:
    return {
        "bookId": str(book.id),
        "workspaceId": str(book.workspace_id),
        "title": book.title,
        "author": book.author,
        "status": book.status,
        "error": book.error,
        "ingestedAt": book.ingested_at.isoformat() if book.ingested_at else None,
    }


@router.post("", status_code=201)
def upload_book_endpoint(
    file: UploadFile,
    background: BackgroundTasks,
    storage: Annotated[ObjectStorage, Depends(get_storage)],
    job: Annotated[AdvanceJob, Depends(get_advance_job)],
    session: Annotated[Session, Depends(get_session)],
    workspace: Annotated[Workspace, Depends(get_existing_workspace)],
) -> dict[str, object]:
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    result = upload_book(
        session,
        storage,
        workspace_id=workspace.id,
        filename=file.filename or "upload.bin",
        data=data,
        mime_type=file.content_type,
    )
    session.commit()
    background.add_task(job, workspace.id, result.book_id)
    return {"bookId": str(result.book_id), "created": result.created, "status": result.status}


@router.post("/{book_id}/ingest")
def ingest_book_endpoint(
    book_id: UUID,
    background: BackgroundTasks,
    job: Annotated[AdvanceJob, Depends(get_advance_job)],
    session: Annotated[Session, Depends(get_session)],
    workspace: Annotated[Workspace, Depends(get_existing_workspace)],
) -> dict[str, object]:
    book = BookRepository(session, workspace.id).get_scoped(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")
    background.add_task(job, workspace.id, book_id)
    return {"bookId": str(book_id), "scheduled": True, "status": book.status}


@router.get("")
def list_books_endpoint(
    session: Annotated[Session, Depends(get_session)],
    workspace: Annotated[Workspace, Depends(get_existing_workspace)],
) -> list[dict[str, object]]:
    books = BookRepository(session, workspace.id).list()
    return [_book_payload(book) for book in books]


@router.get("/{book_id}")
def get_book_endpoint(
    book_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    workspace: Annotated[Workspace, Depends(get_existing_workspace)],
) -> dict[str, object]:
    book = BookRepository(session, workspace.id).get_scoped(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")
    payload = _book_payload(book)
    payload["chapterCount"] = len(ChapterRepository(session, workspace.id, book_id).list())
    payload["chunkCount"] = ChunkRepository(session, workspace.id, book_id).count()
    return payload
