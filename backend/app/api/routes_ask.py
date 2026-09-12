from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_existing_workspace
from app.llm.factory import build_embedding_provider, build_llm_provider
from app.orchestration.ask import AskService, BookNotReadyError
from app.orchestration.ask_schemas import AskResult
from app.persistence.db import get_session
from app.persistence.models import Workspace
from app.retrieval.pgvector_engine import PgVectorRetrievalEngine

router = APIRouter(prefix="/workspaces/{workspace_id}/books/{book_id}", tags=["ask"])


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=50)


@lru_cache
def get_ask_service() -> AskService:
    from fastapi import HTTPException

    from app.core.config import get_settings
    from app.persistence.db import get_session_factory

    settings = get_settings()
    llm = build_llm_provider(settings)
    embeddings = build_embedding_provider(settings)
    if llm is None or embeddings is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM/embedding providers not configured "
                "(set ALW_OPENAI_BASE_URL, ALW_OPENAI_API_KEY, ALW_LLM_MODEL, "
                "ALW_EMBEDDING_MODEL)"
            ),
        )
    return AskService(
        get_session_factory(),
        embeddings=embeddings,
        retrieval=PgVectorRetrievalEngine(get_session_factory()),
        llm=llm,
        model=settings.llm_model,
    )


@router.post("/ask", response_model=AskResult)
def ask_endpoint(
    book_id: UUID,
    request: AskRequest,
    session: Annotated[Session, Depends(get_session)],
    workspace: Annotated[Workspace, Depends(get_existing_workspace)],
    service: Annotated[AskService, Depends(get_ask_service)],
) -> AskResult:
    from app.persistence.repositories import BookRepository

    book = BookRepository(session, workspace.id).get_scoped(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")
    try:
        return service.ask(workspace.id, book_id, request.question, top_k=request.top_k)
    except BookNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
