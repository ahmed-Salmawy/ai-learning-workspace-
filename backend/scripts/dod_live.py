"""Live-LLM Phase 1 DoD confirmation run.

Uses REAL GLM chat LLM for Ask-the-Book generation (the external integration
under test) with deterministic fake embeddings (this GLM account has no
embedding model). Books must be ingested to READY first.

Run from backend/:
    .venv/bin/python scripts/dod_live.py
Prerequisites: TEST/ALW_DATABASE_URL env or ALW_DATABASE_URL in .env pointing
at a Postgres 16 + pgvector instance (docker run -e POSTGRES_PASSWORD=postgres
-p 5433:5432 pgvector/pgvector:pg16).
"""

import json
import sys
import time
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import pymupdf  # noqa: E402

from app.core.metrics import METRICS  # noqa: E402
from app.engines.fakes import InMemoryRoadmapEngine  # noqa: E402
from app.engines.protocols import ExtractedConcept  # noqa: E402
from app.llm.fakes import InMemoryEmbeddingProvider  # noqa: E402
from app.orchestration.ask import AskService  # noqa: E402
from app.orchestration.ingestion.pipeline import IngestionPipeline  # noqa: E402
from app.orchestration.ingestion.service import upload_book  # noqa: E402
from app.persistence.repositories import BookRepository, ChunkRepository  # noqa: E402
from app.retrieval.pgvector_engine import PgVectorRetrievalEngine  # noqa: E402
from app.storage.local import LocalStorage  # noqa: E402

BOOKS = {
    "java": {
        "filename": "java_concurrency.pdf",
        "title": "Java Concurrency Basics",
        "text": (
            "Java concurrency chapter {c} note {p}: the volatile keyword only "
            "guarantees visibility of writes across threads; the increment "
            "count++ is a read-modify-write and is not atomic, so updates can "
            "be lost. Prefer AtomicInteger or synchronized blocks."
        ),
        "on_topic": "Why is count++ not thread-safe even if the variable is volatile?",
        "off_topic": "How do I make an Italian soffritto?",
    },
    "cooking": {
        "filename": "italian_cooking.pdf",
        "title": "Italian Cooking Foundations",
        "text": (
            "Italian cooking chapter {c} note {p}: a proper soffritto slowly "
            "cooks finely diced onion, carrot and celery in olive oil until "
            "sweet and translucent; it is the flavor base of ragù and many "
            "slow-simmered sauces."
        ),
        "on_topic": "How do I make a soffritto and what is it used for?",
        "off_topic": "Why is count++ not thread-safe in Java?",
    },
}


def _make_pdf(title: str, template: str) -> bytes:
    doc = pymupdf.open()
    toc = []
    for chapter in range(1, 3):
        page = doc.new_page()
        toc.append([1, f"Chapter {chapter}", chapter])
        for p in range(4):
            page.insert_textbox(
                (50, 80 + p * 60, 540, 140 + p * 60),
                template.format(c=chapter, p=p),
            )
    doc.set_toc(toc)
    data = doc.tobytes()
    doc.close()
    return data


def _migrate() -> None:
    from alembic.config import Config

    from alembic import command
    from app.core.config import get_settings

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")


def main() -> None:
    from app.core.config import get_settings
    from app.persistence.db import get_session_factory

    settings = get_settings()
    if (
        not settings.openai_base_url
        or not settings.openai_api_key
        or not settings.llm_model
    ):
        raise SystemExit("LLM provider not configured — set ALW_OPENAI_* in backend/.env")
    from app.llm.openai_compat import OpenAICompatLLMProvider

    llm = OpenAICompatLLMProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout=240,
    )
    factory = get_session_factory()
    _migrate()

    storage = LocalStorage(BACKEND_ROOT / "var" / f"dod-live-{uuid.uuid4().hex[:8]}")
    embeddings = InMemoryEmbeddingProvider(dimension=1536)
    ws = uuid.uuid4()

    with factory() as session:
        from app.persistence.models import User, Workspace

        session.add(User(email=f"dod-{uuid.uuid4().hex[:8]}@local", display_name="DoD"))
        session.flush()
        from sqlalchemy import select

        user_row = session.execute(
            select(User.id).order_by(User.created_at.desc())
        ).first()
        assert user_row is not None
        user_id = user_row[0]
        session.add(Workspace(id=ws, owner_user_id=user_id, name="dod-live"))
        session.commit()

    book_ids: dict[str, uuid.UUID] = {}
    chunk_ids: dict[str, set[str]] = {}
    for key, spec in BOOKS.items():
        data = _make_pdf(spec["title"], spec["text"])
        with factory() as session:
            book_id = upload_book(
                session, storage, workspace_id=ws,
                filename=spec["filename"], data=data, mime_type="application/pdf",
            ).book_id
            session.commit()
        pipeline = IngestionPipeline(
            factory,
            storage,
            embedding_provider=embeddings,
            roadmap_engine=InMemoryRoadmapEngine(
                concepts=[
                    ExtractedConcept(
                        name=spec["title"],
                        normalized_name=key,
                        description=None,
                    )
                ],
                relationships=[],
            ),
        )
        pipeline.run_to_completion(ws, book_id)
        with factory() as session:
            book = BookRepository(session, ws).get_scoped(book_id)
            status = book.status if book else "MISSING"
            chunk_ids[key] = {
                str(chunk.id) for chunk in ChunkRepository(session, ws, book_id).all_ordered()
            }
        book_ids[key] = book_id
        print(f"[ingest] {key}: {status}, {len(chunk_ids[key])} chunks")

    service = AskService(
        factory,
        embeddings=embeddings,
        retrieval=PgVectorRetrievalEngine(factory),
        llm=llm,
        model=settings.llm_model,
    )

    failures: list[str] = []
    for key, spec in BOOKS.items():
        for kind, question in (("ON-TOPIC ", spec["on_topic"]), ("OFF-TOPIC", spec["off_topic"])):
            started = time.perf_counter()
            result = service.ask(ws, book_ids[key], question)
            elapsed = time.perf_counter() - started
            leaked = [c for c in result.citations if c.book_id != str(book_ids[key])]
            leaked += [
                c for c in result.citations if c.chunk_id not in chunk_ids[key]
            ]
            print(f"\n=== {key} / {kind.strip()} ({elapsed:.1f}s) ===")
            print(f"Q: {question}")
            print(f"A: {result.answer[:400]}")
            print(
                f"grounded={result.book_grounded} insufficient={result.insufficient_evidence} "
                f"citations={[(c.chapter, c.page_start, c.page_end) for c in result.citations]}"
            )
            if result.general_knowledge_note:
                print(f"note: {result.general_knowledge_note[:200]}")
            if kind.startswith("OFF") and result.book_grounded:
                print(
                    "[warn] off-topic answered as grounded (quality, not leakage)"
                )
            if leaked:
                failures.append(f"{key}/{kind}: {len(leaked)} leaked citations")

    snapshot = METRICS.snapshot()
    llm_calls = {k: v for k, v in snapshot["counters"].items() if k.startswith("llm_")}
    print("\n=== metrics ===")
    print(json.dumps(llm_calls, indent=2))

    if failures:
        print("\nDOD FAILED:")
        for failure in failures:
            print(f" - {failure}")
        raise SystemExit(1)
    print("\nDOD PASSED: zero cross-book citation leakage across all live asks.")


if __name__ == "__main__":
    main()
