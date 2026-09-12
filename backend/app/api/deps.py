from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.persistence.db import get_session
from app.persistence.models import Workspace
from app.persistence.repositories import WorkspaceRepository


def get_existing_workspace(
    workspace_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> Workspace:
    workspace = WorkspaceRepository(session).get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return workspace
