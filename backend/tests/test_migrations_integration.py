import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not set; integration tests need local Postgres 16 + pgvector",
    ),
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {
    "users",
    "workspaces",
    "books",
    "book_sources",
    "chapters",
    "content_chunks",
    "concepts",
    "learning_events",
}


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
    return cfg


def test_migrations_upgrade_and_downgrade_clean() -> None:
    cfg = _alembic_config()
    engine = create_engine(os.environ["TEST_DATABASE_URL"])

    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert EXPECTED_TABLES <= tables

    embedding_type = inspector.get_columns("content_chunks")
    chunk_cols = {col["name"] for col in embedding_type}
    assert {"embedding", "content_hash", "book_id", "workspace_id"} <= chunk_cols

    with engine.begin() as conn:
        vector_ext = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        assert vector_ext == "vector"

    command.downgrade(cfg, "base")
    inspector_after = inspect(engine)
    assert EXPECTED_TABLES.isdisjoint(set(inspector_after.get_table_names()))

    engine.dispose()
