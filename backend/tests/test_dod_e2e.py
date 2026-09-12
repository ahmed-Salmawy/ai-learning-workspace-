"""Phase 1 Definition-of-Done verification (README §39).

Upload 2 books from different domains, ask each independently, assert zero
cross-book citation leakage. Runs against real Postgres 16 + pgvector with
fake LLM/embedding providers (no env keys required); the scripted LLM behaves
per the RAG §2 contract. A live-LLM run is a manual follow-up when
ALW_OPENAI_* credentials are available.
"""

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
from app.core.metrics import METRICS
from app.engines.fakes import InMemoryRoadmapEngine
from app.engines.protocols import ExtractedConcept
from app.llm.fakes import InMemoryEmbeddingProvider
from app.orchestration.ask import AskService
from app.orchestration.ingestion.pipeline import IngestionPipeline
from app.orchestration.ingestion.service import upload_book
from app.persistence.conversation_models import Conversation, Message
from app.persistence.models import User, Workspace
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

JAVA_TEXT = (
    "Java chapter {c} section {p}: the volatile keyword guarantees visibility "
    "but count++ is not atomic; prefer AtomicInteger for thread-safe counters."
)
COOKING_TEXT = (
    "Cooking chapter {c} section {p}: a proper soffritto needs slow-cooked "
    "onion, carrot and celery in olive oil as the flavor base of ragù."
)


def _domain_pdf(template: str, title: str, chapters: int = 2) -> bytes:
    doc = pymupdf.open()
    toc = []
    for chapter in range(1, chapters + 1):
        page = doc.new_page()
        toc.append([1, f"Chapter {chapter}", chapter])
        for p in range(4):
            page.insert_textbox(
                (50, 80 + p * 60, 540, 140 + p * 60),
                template.format(c=chapter, p=p) + f" ({title})",
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


def _ingest(
    factory: sessionmaker, storage: LocalStorage, ws: uuid.UUID, data: bytes, name: str
) -> uuid.UUID:
    session = factory()
    book_id = upload_book(
        session, storage, workspace_id=ws, filename=name,
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
                ExtractedConcept(name=name, normalized_name=name.split(".")[0], description=None)
            ],
            relationships=[],
        ),
    )
    pipeline.run_to_completion(ws, book_id)
    return book_id


def test_dod_two_books_zero_cross_book_leakage(pg_engine: Engine, tmp_path: Path) -> None:
    METRICS.reset()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    storage = LocalStorage(tmp_path / "dod")
    ws = uuid.uuid4()
    seed = factory()
    seed.add(User(email=f"owner-{uuid.uuid4().hex[:8]}@test.local", display_name="O"))
    seed.flush()
    user_row = seed.execute(select(User.id).order_by(User.created_at.desc())).first()
    assert user_row is not None
    seed.add(Workspace(id=ws, owner_user_id=user_row[0], name="dod-ws"))
    seed.commit()
    seed.close()

    book_java = _ingest(factory, storage, ws, _domain_pdf(JAVA_TEXT, "Java"), "java.pdf")
    book_food = _ingest(factory, storage, ws, _domain_pdf(COOKING_TEXT, "Cooking"), "cooking.pdf")
    assert book_java != book_food

    embeddings = InMemoryEmbeddingProvider(dimension=1536)
    retrieval = PgVectorRetrievalEngine(factory)
    question = "chapter passage"

    retrieved_java = retrieval.search(
        workspace_id=ws, book_id=book_java,
        query_embedding=embeddings.embed([question])[0], top_k=8,
    )
    retrieved_food = retrieval.search(
        workspace_id=ws, book_id=book_food,
        query_embedding=embeddings.embed([question])[0], top_k=8,
    )
    assert retrieved_java and retrieved_food

    java_ids = {str(chunk.chunk_id) for chunk in retrieved_java}
    food_ids = {str(chunk.chunk_id) for chunk in retrieved_food}
    assert java_ids.isdisjoint(food_ids), "same chunk cannot belong to two books"
    assert all(chunk.book_id == book_java for chunk in retrieved_java)
    assert all(chunk.book_id == book_food for chunk in retrieved_food)

    def _answer(cited_chunk_id: str) -> str:
        return json.dumps(
            {
                "answer": "Grounded answer per the book passages.",
                "bookGrounded": True,
                "citations": [
                    {"chunkId": cited_chunk_id},
                    {"chunkId": cited_chunk_id},
                ],
                "insufficientEvidence": False,
                "generalKnowledgeNote": "General knowledge aside.",
            }
        )

    ask_java = AskService(
        factory, embeddings=embeddings, retrieval=retrieval,
        llm=ScriptedLLM([_answer(str(retrieved_java[0].chunk_id))]),
    )
    ask_food = AskService(
        factory, embeddings=embeddings, retrieval=retrieval,
        llm=ScriptedLLM([_answer(str(retrieved_food[0].chunk_id))]),
    )

    result_java = ask_java.ask(ws, book_java, "Why is count++ unsafe?")
    result_food = ask_food.ask(ws, book_food, "How do I build a soffritto?")

    assert result_java.book_grounded and result_food.book_grounded
    assert all(c.book_id == str(book_java) for c in result_java.citations)
    assert all(c.book_id == str(book_food) for c in result_food.citations)
    assert all(c.chunk_id in java_ids for c in result_java.citations)
    assert all(c.chunk_id in food_ids for c in result_food.citations)
    java_all = java_ids | food_ids
    leaked = [
        c.chunk_id
        for c in result_java.citations + result_food.citations
        if c.chunk_id not in java_all
    ]
    assert leaked == []

    session = factory()
    conversations = {
        conversation.id: conversation
        for conversation in session.query(Conversation).all()
    }
    assert len(conversations) == 2
    book_messages = [
        message
        for message in session.query(Message).all()
        if message.knowledge_source == "BOOK" and message.citations
    ]
    assert len(book_messages) == 2
    for message in book_messages:
        conversation = conversations[message.conversation_id]
        assert message.workspace_id == ws
        assert message.citations is not None
        assert all(
            citation["bookId"] == str(conversation.book_id)
            for citation in message.citations
        )
        if conversation.book_id == book_java:
            assert all(citation["chunkId"] in java_ids for citation in message.citations)
        else:
            assert all(citation["chunkId"] in food_ids for citation in message.citations)
    session.close()

    snapshot = METRICS.snapshot()
    for stage in ("parse", "chunk", "embed", "extract"):
        ok = snapshot["counters"].get(
            f"ingestion_stage_total{{stage={stage},status=ok}}"
        )
        assert ok == 2, (stage, snapshot)
        assert f"ingestion_stage_seconds{{stage={stage}}}" in snapshot["histograms"]
    assert snapshot["counters"]["ingestion_chunks_inserted_total"] > 0
    assert "retrieval_latency_seconds" in " ".join(snapshot["histograms"])
