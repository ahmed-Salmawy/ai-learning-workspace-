from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    workspace_id: UUID
    book_id: UUID
    chapter_id: UUID | None
    section: str | None
    page_start: int | None
    page_end: int | None
    text: str
    score: float


@runtime_checkable
class RetrievalEngine(Protocol):
    def search(
        self,
        *,
        workspace_id: UUID,
        book_id: UUID,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[RetrievedChunk]: ...
