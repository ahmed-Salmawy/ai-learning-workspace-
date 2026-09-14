import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pymupdf
import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, select, update
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.engines.fakes import InMemoryRoadmapEngine
from app.engines.protocols import ExtractedConcept, ExtractedRelationship
from app.llm.fakes import InMemoryEmbeddingProvider
from app.orchestration.ingestion.pipeline import IngestionPipeline
from app.orchestration.ingestion.service import upload_book
from app.persistence.concept_repositories import (
    ConceptRelationshipRepository,
    ConceptRepository,
)
from app.persistence.models import Concept, ContentChunk, User, Workspace
from app.persistence.repositories import BookRepository, ChunkRepository
from app.storage.local import LocalStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not set; integration tests need local Postgres 16 + pgvector",
    ),
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _small_pdf(chapters: int = 2) -> bytes:
    doc = pymupdf.open()
    toc = []
    for chapter in range(1, chapters + 1):
        page = doc.new_page()
        toc.append([1, f"Chapter {chapter}", chapter])
        for p in range(4):
            page.insert_textbox(
                (50, 80 + p * 60, 540, 140 + p * 60),
                f"Chapter {chapter} paragraph {p} explains retrieval augmented "
                "generation with enough length to form chunks.",
            )
    doc.set_toc(toc)
    data = doc.tobytes()
    doc.close()
    return data


def _concept_set() -> list[ExtractedConcept]:
    return [
        ExtractedConcept(name="RAG", normalized_name="rag", description=None),
        ExtractedConcept(name="Embeddings", normalized_name="embeddings", description=None),
    ]


def _relationship_set() -> list[ExtractedRelationship]:
    return [
        ExtractedRelationship(
            from_concept="Embeddings",
            to_concept="RAG",
            relation="PREREQUISITE_OF",
            confidence=0.9,
        )
    ]


@pytest.fixture(scope="module")
def pg_engine() -> Generator[Engine, None, None]:
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_engine(url)
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    yield engine
    command.downgrade(cfg, "base")
    engine.dispose()


def _seed_workspace(factory: sessionmaker) -> uuid.UUID:
    session = factory()
    session.add(User(email=f"owner-{uuid.uuid4().hex[:8]}@test.local", display_name="O"))
    session.flush()
    user_row = session.execute(select(User.id).order_by(User.created_at.desc())).first()
    ws = uuid.uuid4()
    session.add(Workspace(id=ws, owner_user_id=user_row[0], name="ws"))
    session.commit()
    session.close()
    return ws


def _upload(
    factory: sessionmaker, storage: LocalStorage, ws: uuid.UUID, data: bytes
) -> uuid.UUID:
    session = factory()
    result = upload_book(
        session, storage, workspace_id=ws, filename="book.pdf",
        data=data, mime_type="application/pdf",
    )
    session.commit()
    session.close()
    return result.book_id


def _full_pipeline(
    factory: sessionmaker, storage: LocalStorage
) -> IngestionPipeline:
    return IngestionPipeline(
        factory,
        storage,
        embedding_provider=InMemoryEmbeddingProvider(dimension=384),
        roadmap_engine=InMemoryRoadmapEngine(
            concepts=_concept_set(), relationships=_relationship_set()
        ),
    )


def test_full_pipeline_reaches_ready(pg_engine: Engine, tmp_path: Path) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s1")
    ws = _seed_workspace(factory)
    book_id = _upload(factory, storage, ws, _small_pdf())

    pipeline = _full_pipeline(factory, storage)
    results = pipeline.run_to_completion(ws, book_id)

    assert [r.stage for r in results] == ["parse", "chunk", "embed", "extract"]

    with factory() as session:
        book = BookRepository(session, ws).get_scoped(book_id)
        assert book is not None and book.status == "READY"
        assert book.ingested_at is not None

        chunk_rows = ChunkRepository(session, ws, book_id).all_ordered()
        assert chunk_rows
        assert all(chunk.embedding is not None for chunk in chunk_rows)
        assert all(chunk.embedding_model == "fake-embedding" for chunk in chunk_rows)
        assert all(len(chunk.embedding or []) == 384 for chunk in chunk_rows)

        concept_repo = ConceptRepository(session, ws, book_id)
        assert concept_repo.count() == 2
        assert ConceptRelationshipRepository(session, ws, book_id).count() == 1


def test_embed_stage_is_content_addressed(pg_engine: Engine, tmp_path: Path) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s2")
    ws = _seed_workspace(factory)
    book_id = _upload(factory, storage, ws, _small_pdf(1))

    pipeline = IngestionPipeline(
        factory, storage, embedding_provider=InMemoryEmbeddingProvider(dimension=384)
    )
    pipeline.run_to_completion(ws, book_id)

    with factory() as session:
        chunk_repo = ChunkRepository(session, ws, book_id)
        rows = chunk_repo.all_ordered()
        assert rows
        pending = chunk_repo.chunks_without_embedding("fake-embedding")
        assert pending == []
        chunk_count = len(rows)

        session.execute(
            update(ContentChunk)
            .where(ContentChunk.book_id == book_id)
            .values(embedding_model="old-model")
        )
        session.commit()

    with factory() as session:
        chunk_repo = ChunkRepository(session, ws, book_id)
        pending_after_model_change = chunk_repo.chunks_without_embedding("fake-embedding")
        assert len(pending_after_model_change) == chunk_count

    pipeline.advance(ws, book_id)

    with factory() as session:
        rows = ChunkRepository(session, ws, book_id).all_ordered()
        assert all(chunk.embedding_model == "fake-embedding" for chunk in rows)


def test_concept_extraction_dedup_and_isolation(pg_engine: Engine, tmp_path: Path) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s3")
    ws = _seed_workspace(factory)
    data = _small_pdf(1)

    book_a = _upload(factory, storage, ws, data)
    book_b = _upload(factory, storage, ws, _small_pdf(1))

    pipeline = _full_pipeline(factory, storage)
    pipeline.run_to_completion(ws, book_a)
    pipeline.run_to_completion(ws, book_b)

    with factory() as session:
        concepts_a = ConceptRepository(session, ws, book_a)
        concepts_b = ConceptRepository(session, ws, book_b)
        assert concepts_a.count() == 2
        assert concepts_b.count() == 2

        dup_a = session.execute(
            select(Concept).where(
                Concept.book_id == book_a, Concept.normalized_name == "rag"
            )
        ).scalars().all()
        assert len(dup_a) == 1

        rel_a = ConceptRelationshipRepository(session, ws, book_a)
        assert rel_a.count() == 1

    pipeline.run_to_completion(ws, book_a)

    with factory() as session:
        concepts_a = ConceptRepository(session, ws, book_a)
        assert concepts_a.count() == 2
        assert ConceptRelationshipRepository(session, ws, book_a).count() == 1


def test_failed_extract_stage_resumes(pg_engine: Engine, tmp_path: Path) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s4")
    ws = _seed_workspace(factory)
    book_id = _upload(factory, storage, ws, _small_pdf(1))

    class ExplodingEngine(InMemoryRoadmapEngine):
        calls = 0

        def extract_concepts(
            self,
            *,
            workspace_id: uuid.UUID,
            book_id: uuid.UUID,
            chunk_texts: list[str],
        ) -> list[ExtractedConcept]:
            ExplodingEngine.calls += 1
            if ExplodingEngine.calls >= 1:
                raise RuntimeError("simulated extraction crash")
            return super().extract_concepts(
                workspace_id=workspace_id, book_id=book_id, chunk_texts=chunk_texts
            )

    pipeline = IngestionPipeline(
        factory,
        storage,
        embedding_provider=InMemoryEmbeddingProvider(dimension=384),
        roadmap_engine=ExplodingEngine(concepts=_concept_set(), relationships=[]),
    )
    with pytest.raises(RuntimeError, match="simulated extraction crash"):
        pipeline.run_to_completion(ws, book_id)

    with factory() as session:
        book = BookRepository(session, ws).get_scoped(book_id)
        assert book is not None and book.status == "FAILED"
        assert book.error is not None and book.error["stage"] == "extract"

    healthy = _full_pipeline(factory, storage)
    healthy.run_to_completion(ws, book_id)

    with factory() as session:
        book = BookRepository(session, ws).get_scoped(book_id)
        assert book is not None and book.status == "READY"
        assert ConceptRepository(session, ws, book_id).count() == 2
