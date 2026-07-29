# syntax=docker/dockerfile:1.7
#
# JMeter worker: Apache JMeter plus the agent that runs it.
#
# **This image is the single source of truth for the JMeter version.** The
# version is pinned once, here, and is never selectable by the server, by a
# setting, or by a caller — which is why nothing in the application records or
# transmits an engine version. Upgrading JMeter means changing JMETER_VERSION
# below and rebuilding; there is no runtime switch and no second place to look.

FROM ghcr.io/astral-sh/uv:latest AS uv_bin

FROM eclipse-temurin:21-jre-jammy

ARG JMETER_VERSION=5.6.3

WORKDIR /app

COPY --from=uv_bin /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Apache JMeter, verified against the published SHA-512 checksum. An unverified
# download of something this image then executes would be an obvious supply
# chain hole.
RUN set -eux; \
    cd /opt; \
    curl -fsSL -O "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz"; \
    curl -fsSL -O "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz.sha512"; \
    sha512sum -c "apache-jmeter-${JMETER_VERSION}.tgz.sha512"; \
    tar -xzf "apache-jmeter-${JMETER_VERSION}.tgz"; \
    rm "apache-jmeter-${JMETER_VERSION}.tgz" "apache-jmeter-${JMETER_VERSION}.tgz.sha512"; \
    ln -s "/opt/apache-jmeter-${JMETER_VERSION}/bin/jmeter" /usr/local/bin/jmeter

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# The isolation boundary required by runtime-boundary RB5. Only the trees the
# agent imports — NOT `COPY app ./app`. The worker has no business holding the
# DAO, the dispatcher, OperationService or the ZAP integration, and shipping
# them would leave RB3 ("a runtime never reaches persistence or orchestration")
# resting on convention alone. `app/` is a namespace package, so copying
# subtrees needs no __init__.py.
# tests/integrations/jmeter/test_jmeter_worker_isolation.py fails if the agent's
# import closure ever grows past this list.
COPY app/runtime/jmeter ./app/runtime/jmeter
COPY app/core ./app/core
COPY app/schemas/tools/jmeter ./app/schemas/tools/jmeter
COPY app/integrations/jmeter ./app/integrations/jmeter
COPY config ./config

COPY docker/jmeter/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/jmeter/register-worker.sh /usr/local/bin/register-worker.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/register-worker.sh

EXPOSE 8090

# The entrypoint runs the agent alongside the registration/heartbeat sidecar,
# so a worker announces itself with no server-side configuration — the same
# pattern the ZAP worker uses.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.runtime.jmeter.main:app --host 0.0.0.0 --port ${JMETER_AGENT_PORT:-8090}"]
