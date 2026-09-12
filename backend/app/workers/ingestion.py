from collections.abc import Callable
from functools import lru_cache
from uuid import UUID

from app.core.config import Settings, get_settings
from app.engines.llm_roadmap import LLMRoadmapEngine
from app.engines.protocols import RoadmapEngine
from app.llm.factory import build_embedding_provider, build_llm_provider
from app.orchestration.ingestion.pipeline import IngestionPipeline
from app.persistence.db import get_session_factory
from app.storage.local import LocalStorage

AdvanceJob = Callable[[UUID, UUID], None]


@lru_cache
def get_storage() -> LocalStorage:
    return LocalStorage(get_settings().storage_root)


@lru_cache
def get_pipeline() -> IngestionPipeline:
    settings = get_settings()
    return IngestionPipeline(
        get_session_factory(),
        get_storage(),
        embedding_provider=build_embedding_provider(settings),
        roadmap_engine=_roadmap_engine_from_settings(settings),
    )


def _roadmap_engine_from_settings(settings: Settings) -> RoadmapEngine | None:
    llm = build_llm_provider(settings)
    if llm is None:
        return None
    return LLMRoadmapEngine(llm, model=settings.llm_model)


def get_advance_job() -> AdvanceJob:
    def job(workspace_id: UUID, book_id: UUID) -> None:
        get_pipeline().run_to_completion(workspace_id, book_id)

    return job


def advance_book_job(workspace_id: UUID, book_id: UUID) -> None:
    """Entrypoint for external workers/CLI; not used by the API dependency graph."""
    get_pipeline().run_to_completion(workspace_id, book_id)
