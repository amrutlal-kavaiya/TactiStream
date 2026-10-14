# syntax=docker/dockerfile:1
# Single image: FastAPI API + WebSocket + built SPA (research R6). Probes live in Container Apps, so no HEALTHCHECK.

FROM node:22.23.3-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY contracts/ /src/contracts/
RUN npm run build

FROM python:3.12.15-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# The image mirrors the repo layout under /app so repo-relative defaults (data/, contracts/) still resolve.
COPY backend/pyproject.toml backend/uv.lock backend/README.md backend/
RUN uv sync --frozen --no-dev --no-install-project --project backend
COPY backend/src backend/src
RUN uv sync --frozen --no-dev --project backend
COPY --from=web /src/frontend/dist frontend/dist
COPY contracts/schemas contracts/schemas
COPY data/fixtures data/fixtures
COPY eva[l]/result[s]/lates[t] eval/results/latest

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    TACTISTREAM_STATIC_DIR=/app/frontend/dist \
    TACTISTREAM_CONTRACTS_DIR=/app/contracts/schemas \
    TACTISTREAM_DATA_DIR=/app/data
EXPOSE 8000
CMD ["tactistream-api"]
