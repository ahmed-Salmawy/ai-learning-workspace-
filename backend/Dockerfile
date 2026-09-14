FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

RUN pip install --no-cache-dir '.[dev,embeddings]'

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python scripts/bootstrap_workspace.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
