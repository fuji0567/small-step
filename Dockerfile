FROM node:24.19.0-bookworm-slim AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN mkdir -p /build/app \
    && npm run format:check \
    && npm run lint \
    && npm run check \
    && npm run test:unit \
    && npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY app ./app
COPY --from=frontend-build /build/app/frontend_dist ./app/frontend_dist
COPY migrations ./migrations
COPY scripts ./scripts
RUN pip install --upgrade pip && pip install .[postgres]

RUN useradd --create-home --uid 10001 appuser \
    && mkdir --parents /app/data \
    && chmod --recursive a+rX /app \
    && chown appuser:appuser /app/data
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
