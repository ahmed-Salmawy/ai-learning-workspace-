"""Create the default Phase 1 development workspace.

Run from backend/ with the project venv:
    .venv/bin/python scripts/bootstrap_workspace.py

Prints the workspace id (defaults to 00000000-0000-0000-0000-000000000001)
that the frontend uses via NEXT_PUBLIC_WORKSPACE_ID.
"""

import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.persistence.db import get_session_factory  # noqa: E402
from app.persistence.models import User, Workspace  # noqa: E402

DEFAULT_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def main() -> None:
    factory = get_session_factory()
    settings = get_settings()
    engine = factory.kw["bind"]
    engine.dispose()

    with factory() as session:
        existing = session.get(Workspace, DEFAULT_WORKSPACE_ID)
        if existing is not None:
            print(f"workspace already exists: {DEFAULT_WORKSPACE_ID}")
            return
        user = User(email="bootstrap@local", display_name="Bootstrap Owner")
        session.add(user)
        session.flush()
        session.add(
            Workspace(
                id=DEFAULT_WORKSPACE_ID,
                owner_user_id=user.id,
                name=f"Default ({settings.environment})",
            )
        )
        session.commit()
    print(f"workspace created: {DEFAULT_WORKSPACE_ID}")


if __name__ == "__main__":
    main()
