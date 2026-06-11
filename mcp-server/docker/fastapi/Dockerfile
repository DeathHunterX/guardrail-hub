# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:latest AS uv_bin

FROM python:3.12-slim

WORKDIR /app

COPY --from=uv_bin /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY config ./config

RUN mkdir -p /app/data /app/logs /app/reports

EXPOSE 8787

CMD ["sh", "-c", "uvicorn app.main:app --host ${MCP_SERVER_HOST:-0.0.0.0} --port ${MCP_SERVER_PORT:-8787}"]
