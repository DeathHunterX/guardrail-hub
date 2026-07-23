# syntax=docker/dockerfile:1.7
#
# Apache JMeter — Performance Engine (standalone infrastructure image).
#
# This image only provides the JMeter CLI in non-GUI (headless) mode. It has
# no knowledge of the mcp-server application; the future Runner (Service ->
# Runner -> Docker/CLI Engine, mirroring docker/owasp_zap) invokes this image
# per execution rather than talking to a long-running daemon, since `jmeter
# -n` runs one test plan to completion and exits. There is no
# register-worker.sh sidecar here — that pattern exists for ZAP's persistent
# worker pool and does not apply to a one-shot CLI tool.
FROM eclipse-temurin:17-jre-jammy

# JMeter version is HARD-PINNED here, not a build ARG: it cannot be overridden
# from docker-compose or the CLI. Changing it is a deliberate edit to this
# file — and the tarball's SHA-512 is re-verified against Apache's published
# checksum at build time, so a bad/mistyped version fails the build rather
# than silently producing a different image.
ENV JMETER_VERSION=5.6.3 \
    JMETER_HOME=/opt/jmeter \
    PATH=/opt/jmeter/bin:${PATH} \
    # Headless/non-GUI mode never needs a display; set defensively so any
    # AWT-touching JMeter component (e.g. some listeners) does not attempt to
    # open one.
    JVM_ARGS="-Djava.awt.headless=true" \
    # Fixed, stable JVM heap for the `jmeter` launch script (it honors HEAP).
    # min == max (1 GB) avoids GC heap-resizing pauses mid-run, so timings are
    # repeatable; MaxMetaspaceSize matches JMeter's own stock default. Baked
    # into the image so every run is identical — not tuned per-invocation.
    HEAP="-Xms1g -Xmx1g -XX:MaxMetaspaceSize=256m"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The download loop tries the Fastly-fronted CDN (dlcdn) first — fast, and
# reachable on many networks that block archive.apache.org — then falls back
# to the permanent archive. Both use `curl -f` so an HTTP error is a real
# failure, not a silently-saved error page; the tarball is then checksum-
# verified against Apache's published SHA-512 before extraction. (Comments are
# kept OUT of the RUN block below so the `\` line-continuations are
# unambiguous.)
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

# Working directories for the future Runner. These are separate from
# JMETER_HOME (the binary distribution) and are the mount points bind-mounted
# by docker-compose.yml:
#   /jmeter/test-plans -> mcp-server/docker/jmeter/test-plans (ro, versioned)
#   /jmeter/reports    -> mcp-server/reports/jmeter (JTL + HTML dashboard)
#   /jmeter/logs       -> mcp-server/logs/jmeter (jmeter.log)
#   /jmeter/tmp        -> mcp-server/data/jmeter/tmp (scratch space)
#   /jmeter/artifacts  -> mcp-server/data/jmeter/artifacts (future exports)
RUN mkdir -p /jmeter/test-plans /jmeter/reports /jmeter/logs /jmeter/tmp /jmeter/artifacts \
    && groupadd --gid 1000 jmeter \
    && useradd --uid 1000 --gid jmeter --shell /bin/bash --create-home jmeter \
    && chown -R jmeter:jmeter "${JMETER_HOME}" /jmeter

USER jmeter
WORKDIR /jmeter

# No default CMD: this image is a CLI tool, not a service. Callers always
# supply JMeter's own flags, e.g.:
#   docker run --rm <image> -n -t /jmeter/test-plans/smoke-test.jmx \
#     -l /jmeter/reports/smoke-test.jtl -j /jmeter/logs/jmeter.log
ENTRYPOINT ["jmeter"]
