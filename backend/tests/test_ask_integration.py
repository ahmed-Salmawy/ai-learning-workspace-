import json
import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pymupdf
import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.api.routes_ask import get_ask_service as get_ask_service_dep
from app.engines.fakes import InMemoryRoadmapEngine
from app.engines.protocols import ExtractedConcept
from app.llm.fakes import InMemoryEmbeddingProvider
from app.orchestration.ask import AskService, BookNotReadyError
from app.orchestration.ingestion.pipeline import IngestionPipeline
from app.orchestration.ingestion.service import upload_book
from app.persistence.conversation_models import Conversation, KnowledgeSource, Message
from app.persistence.models import User, Workspace
from app.persistence.repositories import BookRepository
from app.retrieval.pgvector_engine import PgVectorRetrievalEngine
from app.storage.local import LocalStorage
from tests.scripted import ScriptedLLM

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not set; integration tests need local Postgres 16 + pgvector",
    ),
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _pdf(pages: int = 2) -> bytes:
    doc = pymupdf.open()
    toc = []
    for chapter in range(1, pages + 1):
        page = doc.new_page()
        toc.append([1, f"Chapter {chapter}", chapter])
        for p in range(4):
            page.insert_textbox(
                (50, 80 + p * 60, 540, 140 + p * 60),
                f"Chapter {chapter} passage {p}: volatile variables are useful for "
                "visibility but count++ is not atomic; use AtomicInteger instead.",
            )
    doc.set_toc(toc)
    data = doc.tobytes()
    doc.close()
    return data


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


def _ingest_to_ready(
    factory: sessionmaker, storage: LocalStorage, ws: uuid.UUID, data: bytes
) -> uuid.UUID:
    session = factory()
    book_id = upload_book(
        session, storage, workspace_id=ws, filename="book.pdf",
        data=data, mime_type="application/pdf",
    ).book_id
    session.commit()
    session.close()

    pipeline = IngestionPipeline(
        factory,
        storage,
        embedding_provider=InMemoryEmbeddingProvider(dimension=1536),
        roadmap_engine=InMemoryRoadmapEngine(
            concepts=[
                ExtractedConcept(
                    name="Atomicity", normalized_name="atomicity", description=None
                )
            ],
            relationships=[],
        ),
    )
    pipeline.run_to_completion(ws, book_id)
    return book_id


def _ask_service(
    factory: sessionmaker, llm_responses: list[str]
) -> AskService:
    return AskService(
        factory,
        embeddings=InMemoryEmbeddingProvider(dimension=1536),
        retrieval=PgVectorRetrievalEngine(factory),
        llm=ScriptedLLM(llm_responses),
    )


def test_ask_returns_grounded_answer_with_provenance(
    pg_engine: Engine, tmp_path: Path
) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s1")
    ws = _seed_workspace(factory)
    book_id = _ingest_to_ready(factory, storage, ws, _pdf())

    question = "Why is count++ not thread safe?"
    embeddings = InMemoryEmbeddingProvider(dimension=1536)
    retrieval = PgVectorRetrievalEngine(factory)
    retrieved = retrieval.search(
        workspace_id=ws,
        book_id=book_id,
        query_embedding=embeddings.embed([question])[0],
        top_k=3,
    )
    assert retrieved, "expected chunks retrieved for the question"
    cited_chunk = retrieved[0]

    answer_json = json.dumps(
        {
            "answer": "count++ is not atomic, so increments can be lost (Ch. 1).",
            "bookGrounded": True,
            "citations": [{"chunkId": str(cited_chunk.chunk_id)}],
            "insufficientEvidence": False,
            "generalKnowledgeNote": "AtomicInteger uses CAS instructions.",
        }
    )
    service = _ask_service(factory, [answer_json])

    result = service.ask(ws, book_id, question)

    assert result.book_grounded is True
    assert result.insufficient_evidence is False
    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.chunk_id == str(cited_chunk.chunk_id)
    assert citation.book_id == str(book_id)
    assert citation.chapter in {1, 2}
    assert citation.page_start is not None

    session = factory()
    conversations = session.query(Conversation).all()
    assert len(conversations) == 1
    messages = (
        session.query(Message)
        .filter(Message.conversation_id == conversations[0].id)
        .all()
    )
    by_role = sorted((m.role, m.knowledge_source) for m in messages)
    assert ("USER", KnowledgeSource.LEARNER) in by_role
    assert ("ASSISTANT", KnowledgeSource.BOOK) in by_role
    assert ("ASSISTANT", KnowledgeSource.SYSTEM) in by_role
    assistant_book = next(
        m for m in messages if m.knowledge_source == KnowledgeSource.BOOK
    )
    assert assistant_book.citations is not None
    assert assistant_book.citations[0]["chunkId"] == str(cited_chunk.chunk_id)
    session.close()


def test_ask_insufficient_evidence_returns_exact_contract(
    pg_engine: Engine, tmp_path: Path
) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s2")
    ws = _seed_workspace(factory)
    book_id = _ingest_to_ready(factory, storage, ws, _pdf(1))

    answer_json = json.dumps(
        {
            "answer": "I have no idea.",
            "bookGrounded": True,
            "citations": [],
            "insufficientEvidence": True,
            "generalKnowledgeNote": None,
        }
    )
    service = _ask_service(factory, [answer_json])

    result = service.ask(ws, book_id, "What is the meaning of life per this book?")

    assert result.insufficient_evidence is True
    assert result.book_grounded is False
    assert result.citations == []
    assert result.answer == (
        "I could not find enough material in this book to answer confidently."
    )

    session = factory()
    messages = session.query(Message).all()
    assert [m.content for m in messages].count(
        "I could not find enough material in this book to answer confidently."
    ) == 1
    session.close()


def test_ask_never_trusts_invented_citations(pg_engine: Engine, tmp_path: Path) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s3")
    ws = _seed_workspace(factory)
    book_id = _ingest_to_ready(factory, storage, ws, _pdf(1))

    invented_chunk_id = str(uuid.uuid4())
    answer_json = json.dumps(
        {
            "answer": "Fabricated answer claiming a passage.",
            "bookGrounded": True,
            "citations": [{"chunkId": invented_chunk_id}],
            "insufficientEvidence": False,
            "generalKnowledgeNote": None,
        }
    )
    service = _ask_service(factory, [answer_json])

    result = service.ask(ws, book_id, "Anything about volatile?")

    assert result.insufficient_evidence is True
    assert result.book_grounded is False
    assert result.citations == []
    assert result.answer.startswith("I could not find enough material")


def test_ask_isolated_between_books(pg_engine: Engine, tmp_path: Path) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s4")
    ws = _seed_workspace(factory)
    book_a = _ingest_to_ready(factory, storage, ws, _pdf(2))
    book_b = _ingest_to_ready(factory, storage, ws, _pdf(2))

    retrieval = PgVectorRetrievalEngine(factory)
    embeddings = InMemoryEmbeddingProvider(dimension=1536)
    question = "count++ visibility atomic"

    results_a = retrieval.search(
        workspace_id=ws, book_id=book_a,
        query_embedding=embeddings.embed([question])[0], top_k=8,
    )
    results_b = retrieval.search(
        workspace_id=ws, book_id=book_b,
        query_embedding=embeddings.embed([question])[0], top_k=8,
    )
    assert results_a and results_b
    assert all(chunk.book_id == book_a for chunk in results_a)
    assert all(chunk.book_id == book_b for chunk in results_b)

    cited_b = results_b[0]
    answer_json = json.dumps(
        {
            "answer": "Answer citing a passage.",
            "bookGrounded": True,
            "citations": [{"chunkId": str(cited_b.chunk_id)}],
            "insufficientEvidence": False,
            "generalKnowledgeNote": None,
        }
    )
    service = _ask_service(factory, [answer_json])
    result = service.ask(ws, book_a, question)

    assert all(citation.book_id == str(book_a) for citation in result.citations)
    assert all(
        citation.chunk_id != str(cited_b.chunk_id) for citation in result.citations
    ) or not result.citations


def test_ask_rejects_book_not_ready(pg_engine: Engine, tmp_path: Path) -> None:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s5")
    ws = _seed_workspace(factory)

    session = factory()
    book_id = upload_book(
        session, storage, workspace_id=ws, filename="notready.pdf",
        data=_pdf(1), mime_type="application/pdf",
    ).book_id
    session.commit()
    session.close()

    service = _ask_service(factory, ["{}"])

    with pytest.raises(BookNotReadyError):
        service.ask(ws, book_id, "hello?")

    session = factory()
    book = BookRepository(session, ws).get_scoped(book_id)
    assert book is not None and book.status == "UPLOADED"
    session.close()


def test_ask_endpoint_wiring_and_status_mapping(
    pg_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.persistence.db import get_session
    from app.workers.ingestion import get_storage

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "s6")
    ws = _seed_workspace(factory)
    book_id = _ingest_to_ready(factory, storage, ws, _pdf(1))

    def override_session() -> Generator[object, None, None]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    embeddings = InMemoryEmbeddingProvider(dimension=1536)
    retrieved = PgVectorRetrievalEngine(factory).search(
        workspace_id=ws,
        book_id=book_id,
        query_embedding=embeddings.embed(["volatile"])[0],
        top_k=1,
    )
    assert retrieved
    answer_json = json.dumps(
        {
            "answer": "Grounded answer (Ch. 1).",
            "bookGrounded": True,
            "citations": [{"chunkId": str(retrieved[0].chunk_id)}],
            "insufficientEvidence": False,
            "generalKnowledgeNote": None,
        }
    )

    def override_ask_service() -> AskService:
        return _ask_service(factory, [answer_json])

    monkeypatch.setenv("ALW_STORAGE_ROOT", str(tmp_path / "s6"))
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_ask_service_dep] = override_ask_service
    try:
        with TestClient(app) as client:
            ok = client.post(
                f"/workspaces/{ws}/books/{book_id}/ask",
                json={"question": "What about volatile?"},
            )
            assert ok.status_code == 200, ok.text
            body = ok.json()
            assert body["bookGrounded"] is True
            assert "conversationId" in body

            not_ready = uuid.uuid4()
            unknown = client.post(
                f"/workspaces/{ws}/books/{not_ready}/ask",
                json={"question": "hi"},
            )
            assert unknown.status_code == 404

            session = factory()
            from app.orchestration.ingestion.service import upload_book as _up

            fresh = _up(
                session, storage, workspace_id=ws, filename="fresh.pdf",
                data=_pdf(1), mime_type="application/pdf",
            ).book_id
            session.commit()
            session.close()

            conflict = client.post(
                f"/workspaces/{ws}/books/{fresh}/ask",
                json={"question": "hi"},
            )
            assert conflict.status_code == 409
    finally:
        app.dependency_overrides.clear()
