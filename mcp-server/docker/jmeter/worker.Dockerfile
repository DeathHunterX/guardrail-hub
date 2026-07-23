# syntax=docker/dockerfile:1.7
#
# Apache JMeter — Performance Engine WARM WORKER image.
#
# Unlike docker/jmeter/Dockerfile (a one-shot `jmeter` CLI image), this is the
# long-lived pull-model worker (ADR-0010 §4.2): a Python process that registers
# with the mcp-server, heartbeats, pulls one assignment at a time, and runs a
# short-lived `jmeter -n` subprocess per job inside a workspace the Runtime owns.
# It therefore needs BOTH the JMeter CLI (the engine the runner invokes) and the
# mcp-server Python app (the worker composition + loop). The container entrypoint
# is the worker's composition root, app/workers/performance_worker.py.
#
# The image is self-contained (it installs its own pinned JMeter) so it never
# depends on the CLI image being built or tagged first. Non-root by construction.
FROM eclipse-temurin:17-jre-jammy

# ── JMeter (hard-pinned + checksum-verified, identical to the CLI image) ──────
ENV JMETER_VERSION=5.6.3 \
    JMETER_HOME=/opt/jmeter \
    PATH=/opt/jmeter/bin:/app/.venv/bin:${PATH} \
    JVM_ARGS="-Djava.awt.headless=true" \
    HEAP="-Xms1g -Xmx1g -XX:MaxMetaspaceSize=256m" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Fastly-fronted CDN first (reachable where archive.apache.org is blocked), then
# the permanent archive; `curl -f` so an HTTP error is a real failure, and the
# tarball is SHA-512-verified against Apache's published checksum before extract.
RUN set -eux; \
    for base in \
        "https://dlcdn.apache.org/jmeter/binaries" \
        "https://archive.apache.org/dist/jmeter/binaries"; do \
        if curl -fsSL -o /tmp/jmeter.tgz "${base}/apache-jmeter-${JMETER_VERSION}.tgz" \
           && curl -fsSL -o /tmp/jmeter.tgz.sha512 "${base}/apache-jmeter-${JMETER_VERSION}.tgz.sha512"; then \
            break; \
        fi; \
    done; \
    test -s /tmp/jmeter.tgz; \
    cd /tmp; \
    echo "$(awk '{print $1}' jmeter.tgz.sha512)  jmeter.tgz" | sha512sum -c -; \
    mkdir -p "${JMETER_HOME}"; \
    tar -xzf jmeter.tgz -C "${JMETER_HOME}" --strip-components=1; \
    rm -f jmeter.tgz jmeter.tgz.sha512; \
    jmeter --version

# ── Python app + dependencies (uv, mirroring docker/fastapi/Dockerfile) ───────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY app ./app

# ── Non-root worker user + writable workspace/log roots ───────────────────────
# The worker writes only under its workspace root (one isolated tree per job,
# destroyed after report — INV2/INV5). uid/gid 1000 matches the CLI image.
RUN mkdir -p /jmeter/workspaces /jmeter/logs \
    && groupadd --gid 1000 jmeter \
    && useradd --uid 1000 --gid jmeter --shell /bin/bash --create-home jmeter \
    && chown -R jmeter:jmeter "${JMETER_HOME}" /jmeter /app

USER jmeter
WORKDIR /app

# Sensible in-image defaults; every value is overridable from docker-compose.
ENV MCP_SERVER_INTERNAL_URL=http://mcp-server:8787 \
    PERFORMANCE_WORKER_WORKSPACE_DIR=/jmeter/workspaces \
    PERFORMANCE_WORKER_HEARTBEAT_INTERVAL_SECONDS=5 \
    JMETER_BINARY=jmeter

# `exec`-form so the Python process is PID 1 and receives SIGTERM directly — the
# worker installs a handler that stops its loop cleanly (docker stop).
ENTRYPOINT ["python3", "-m", "app.workers.performance_worker"]
