# build stage: resolve and install dependencies into a project-local venv
FROM python:3.13-slim AS builder

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

RUN pip install --no-cache-dir poetry==2.4.1

WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
# install third-party deps first so this layer caches across code changes
RUN poetry install --only main --no-root --no-cache

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN poetry install --only main --no-cache

# runtime stage: no poetry, no build tooling, non-root user
FROM python:3.13-slim

RUN useradd --create-home appuser
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
