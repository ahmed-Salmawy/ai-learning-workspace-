import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pymupdf
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.main import app
from app.orchestration.ingestion.extract import ExtractedDocument
from app.orchestration.ingestion.pipeline import IngestionPipeline
from app.persistence.db import get_session
from app.persistence.models import User, Workspace
from app.storage.local import LocalStorage
from app.workers.ingestion import get_advance_job, get_pipeline, get_storage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not set; integration tests need local Postgres 16 + pgvector",
    ),
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class TestContext:
    workspace_id: uuid.UUID


def _tiny_pdf(chapters: int = 3, paragraphs_per_page: int = 6) -> bytes:
    doc = pymupdf.open()
    toc = []
    for chapter in range(1, chapters + 1):
        page = doc.new_page()
        toc.append([1, f"Chapter {chapter}", chapter])
        for p in range(paragraphs_per_page):
            text = (
                f"Chapter {chapter} paragraph {p}. This text discusses the ideas of "
                "machine learning with enough length to form meaningful chunk content "
                "for the ingestion pipeline tests."
            )
            page.insert_textbox((50, 80 + p * 60, 540, 140 + p * 60), text)
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


@pytest.fixture
def client(
    pg_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    test_session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "storage")
    pipeline = IngestionPipeline(test_session_factory, storage)

    def override_session() -> Generator[object, None, None]:
        session = test_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def override_job() -> object:
        def job(workspace_id: uuid.UUID, book_id: uuid.UUID) -> None:
            pipeline.run_to_completion(workspace_id, book_id)

        return job

    monkeypatch.setenv("ALW_STORAGE_ROOT", str(tmp_path / "storage"))
    seed_session = test_session_factory()
    seed_session.add(
        User(email=f"owner-{uuid.uuid4().hex[:8]}@test.local", display_name="Owner")
    )
    seed_session.flush()
    seed_workspace_id = uuid.uuid4()
    user_row = seed_session.execute(select(User.id).order_by(User.created_at.desc())).first()
    user_id = user_row[0] if user_row else None
    assert user_id is not None
    seed_session.add(
        Workspace(id=seed_workspace_id, owner_user_id=user_id, name="test-ws")
    )
    seed_session.commit()
    seed_session.close()
    TestContext.workspace_id = seed_workspace_id

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_advance_job] = override_job
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _upload(
    client: TestClient, data: bytes, name: str = "book.pdf"
) -> dict:
    response = client.post(
        f"/workspaces/{TestContext.workspace_id}/books",
        files={"file": (name, data, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _book(client: TestClient, workspace_id: uuid.UUID, book_id: uuid.UUID) -> dict:
    response = client.get(f"/workspaces/{workspace_id}/books/{book_id}")
    assert response.status_code == 200
    return dict(response.json())


def test_upload_ingest_and_dedup_round_trip(client: TestClient, pg_engine: Engine) -> None:
    ws = TestContext.workspace_id
    data = _tiny_pdf()

    uploaded = _upload(client, data)
    book_id = uuid.UUID(str(uploaded["bookId"]))
    assert uploaded["created"] is True

    book = _book(client, ws, book_id)
    assert book["status"] == "CHUNKED"
    assert book["chapterCount"] >= 3
    assert book["chunkCount"] > 0

    chunk_count = int(book["chunkCount"])

    re_uploaded = _upload(client, data)
    assert re_uploaded["created"] is False
    assert re_uploaded["bookId"] == str(book_id)

    listing = client.get(f"/workspaces/{ws}/books").json()
    assert len(listing) == 1

    reingest = client.post(f"/workspaces/{ws}/books/{book_id}/ingest")
    assert reingest.status_code == 200
    book_after = _book(client, ws, book_id)
    assert book_after["status"] == "CHUNKED"
    assert book_after["chunkCount"] == chunk_count


def test_same_file_in_second_workspace_is_isolated(
    client: TestClient, pg_engine: Engine
) -> None:
    ws_a = TestContext.workspace_id
    data = _tiny_pdf(2)

    book_a = uuid.UUID(str(_upload(client, data)["bookId"]))

    seed_session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    ws_b = uuid.uuid4()
    user_row = seed_session.execute(select(User.id).order_by(User.created_at.desc())).first()
    user_id = user_row[0] if user_row else None
    assert user_id is not None
    seed_session.add(Workspace(id=ws_b, owner_user_id=user_id, name="second-ws"))
    seed_session.commit()

    import io

    upload_b = client.post(
        f"/workspaces/{ws_b}/books",
        files={"file": ("book.pdf", io.BytesIO(data).read(), "application/pdf")},
    )
    assert upload_b.status_code == 201, upload_b.text
    book_b = uuid.UUID(str(upload_b.json()["bookId"]))
    seed_session.close()

    assert book_a != book_b
    assert client.get(f"/workspaces/{ws_a}/books/{book_b}").status_code == 404

    assert len(client.get(f"/workspaces/{ws_a}/books").json()) == 1
    assert len(client.get(f"/workspaces/{ws_b}/books").json()) == 1


def test_failed_chunk_stage_resumes_without_duplicates(
    client: TestClient, pg_engine: Engine, tmp_path: Path
) -> None:
    from app.orchestration.ingestion.extractors import PyMuPDFTextExtractor
    from app.orchestration.ingestion.service import upload_book
    from app.persistence.repositories import BookRepository, ChunkRepository

    test_session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "storage-resume")

    class ExplodingExtractor(PyMuPDFTextExtractor):
        calls = 0

        def extract(self, data: bytes) -> ExtractedDocument:
            ExplodingExtractor.calls += 1
            if ExplodingExtractor.calls >= 2:
                raise RuntimeError("simulated chunk-stage crash")
            return super().extract(data)

    seed_session = test_session_factory()
    seed_session.add(User(email=f"owner-{uuid.uuid4().hex[:8]}@test.local", display_name="O"))
    seed_session.flush()
    ws = uuid.uuid4()
    user_row = seed_session.execute(select(User.id).order_by(User.created_at.desc())).first()
    user_id = user_row[0] if user_row else None
    assert user_id is not None
    seed_session.add(Workspace(id=ws, owner_user_id=user_id, name="resume-ws"))
    seed_session.commit()
    seed_session.close()

    data = _tiny_pdf(2)

    upload_session = test_session_factory()
    result = upload_book(
        upload_session,
        storage,
        workspace_id=ws,
        filename="resume.pdf",
        data=data,
        mime_type="application/pdf",
    )
    upload_session.commit()
    book_id = result.book_id
    upload_session.close()

    pipeline = IngestionPipeline(test_session_factory, storage, extractor=ExplodingExtractor())
    with pytest.raises(RuntimeError, match="simulated chunk-stage crash"):
        pipeline.run_to_completion(ws, book_id)

    failed_session = test_session_factory()
    book = BookRepository(failed_session, ws).get_scoped(book_id)
    assert book is not None and book.status == "FAILED"
    assert book.error is not None and book.error.get("stage") == "chunk"
    failed_session.close()

    healthy = IngestionPipeline(test_session_factory, storage, extractor=PyMuPDFTextExtractor())
    healthy.run_to_completion(ws, book_id)

    verify_session = test_session_factory()
    recovered = BookRepository(verify_session, ws).get_scoped(book_id)
    assert recovered is not None and recovered.status == "CHUNKED"
    chunk_count = ChunkRepository(verify_session, ws, book_id).count()
    verify_session.close()

    healthy.run_to_completion(ws, book_id)
    verify_session = test_session_factory()
    assert ChunkRepository(verify_session, ws, book_id).count() == chunk_count
    verify_session.close()
