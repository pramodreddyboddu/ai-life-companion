FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential libpq-dev curl \
    && pip install --no-cache-dir "poetry==$POETRY_VERSION" \
    && poetry config virtualenvs.create false \
    && rm -rf /var/lib/apt/lists/*

COPY api/pyproject.toml /app/pyproject.toml
COPY api/poetry.lock /app/poetry.lock

RUN poetry install --no-root --no-interaction

COPY api /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
