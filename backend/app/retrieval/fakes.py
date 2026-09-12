from collections.abc import Sequence
from uuid import UUID

from app.retrieval.protocols import RetrievedChunk


class InMemoryRetrievalEngine:
    def __init__(self, chunks: Sequence[RetrievedChunk] = ()) -> None:
        self._chunks = list(chunks)

    def add(self, chunk: RetrievedChunk) -> None:
        self._chunks.append(chunk)

    def search(
        self,
        *,
        workspace_id: UUID,
        book_id: UUID,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        return [
            chunk
            for chunk in self._chunks
            if chunk.workspace_id == workspace_id and chunk.book_id == book_id
        ][:top_k]
