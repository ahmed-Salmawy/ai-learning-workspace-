import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.metrics import METRICS
from app.persistence.models import ContentChunk
from app.retrieval.protocols import RetrievedChunk


class PgVectorRetrievalEngine:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def search(
        self,
        *,
        workspace_id: UUID,
        book_id: UUID,
        query_embedding: list[float],
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        distance = ContentChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(ContentChunk, distance.label("distance"))
            .where(
                ContentChunk.workspace_id == workspace_id,
                ContentChunk.book_id == book_id,
                ContentChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(top_k)
        )
        start = time.perf_counter()
        with self._session_factory() as session:
            rows = session.execute(stmt).all()
        METRICS.observe("retrieval_latency_seconds", time.perf_counter() - start)
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                workspace_id=chunk.workspace_id,
                book_id=chunk.book_id,
                chapter_id=chunk.chapter_id,
                section=chunk.section,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                text=chunk.text,
                score=1.0 - float(row_distance),
            )
            for chunk, row_distance in rows
        ]
