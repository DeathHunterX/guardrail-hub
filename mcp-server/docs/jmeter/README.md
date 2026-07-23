# Apache JMeter — Performance Engine (Infrastructure Setup)

> **Status: infrastructure only.** This page documents the Docker image and
> directory layout added for JMeter. No MCP tool, Service, or Runner exists
> yet — see [Where things live](#where-things-live-for-contributors) for
> what's next.

Guardrail Hub treats JMeter as a **Performance Engine**, mirroring the
layering already used for the OWASP ZAP integration:

```
MCP Tool -> Service -> Runner -> Docker/CLI Engine
```

Unlike ZAP, JMeter is not a long-running daemon with a worker pool: `jmeter
-n` (non-GUI mode) runs one test plan to completion and exits. So there is no
self-registration sidecar, no heartbeat, and no worker registry for it — the
future Runner invokes the image per execution, the same way a CLI tool is
invoked.

## Docker image

| | |
|---|---|
| Dockerfile | [`docker/jmeter/Dockerfile`](../../docker/jmeter/Dockerfile) |
| Base image | `eclipse-temurin:17-jre-jammy` |
| JMeter version | `5.6.3` — **hard-pinned in the Dockerfile** (`ENV JMETER_VERSION`), not overridable from compose/CLI |
| JVM heap | `-Xms1g -Xmx1g -XX:MaxMetaspaceSize=256m` — **hard-pinned** (`ENV HEAP`); min == max avoids GC resizing pauses for repeatable timings |
| Source | `dlcdn.apache.org` (Fastly CDN) first, falling back to `archive.apache.org` — both fetched with `curl -f` and verified against Apache's published SHA-512 before extraction |
| Entrypoint | `jmeter` (the image is a CLI tool — every invocation supplies JMeter's own flags) |
| Runs as | non-root user `jmeter` (uid/gid 1000) |

### Build

```bash
cd mcp-server
docker compose build jmeter
# or directly:
docker build -f docker/jmeter/Dockerfile -t guardrail-jmeter:local .
```

### Run (smoke test)

```bash
# Via compose (recommended — wires up all five mounted directories below)
docker compose --profile jmeter up jmeter

# Or ad hoc, for an arbitrary future test plan:
docker compose --profile jmeter run --rm jmeter \
  -n -t /jmeter/test-plans/smoke-test.jmx \
  -l /jmeter/reports/smoke-test.jtl \
  -j /jmeter/logs/jmeter.log
```

A successful run exits `0` and produces `reports/jmeter/smoke-test.jtl`
(non-empty, containing one sample line) plus `logs/jmeter/jmeter.log`. There
is no network egress in the bundled smoke-test plan (see below), so a
container without external internet access should still pass it.

## Mounted volumes

| Host path (`mcp-server/`) | Container path | Purpose | Mode |
|---|---|---|---|
| `docker/jmeter/test-plans/` | `/jmeter/test-plans` | Versioned `.jmx` test plans | read-only |
| `reports/jmeter/` | `/jmeter/reports` | JTL results + HTML dashboards | read-write |
| `logs/jmeter/` | `/jmeter/logs` | JMeter's own run log (`jmeter.log`) | read-write |
| `data/jmeter/tmp/` | `/jmeter/tmp` | Scratch space for a run | read-write |
| `data/jmeter/artifacts/` | `/jmeter/artifacts` | Future exported artifacts (CSVs, screenshots, etc.) | read-write |

`reports/`, `logs/`, and `data/` are gitignored at the `mcp-server/` root
(runtime output), matching the existing `data/zap/` / `reports/zap/`
convention — only `docker/jmeter/test-plans/` is version-controlled, since
test plans are an input artifact, not runtime output.

## Environment variables

None. Both the JMeter version and the JVM heap are **hard-pinned inside
[`docker/jmeter/Dockerfile`](../../docker/jmeter/Dockerfile)** and are
intentionally not exposed as environment variables — every run uses the exact
same engine and heap, so results are reproducible and can't drift from a
stray `.env` value.

| Setting | Fixed value | Where |
|---|---|---|
| JMeter version | `5.6.3` | `ENV JMETER_VERSION` (Dockerfile) |
| JVM heap | `-Xms1g -Xmx1g -XX:MaxMetaspaceSize=256m` | `ENV HEAP` (Dockerfile) |

To change either, edit the Dockerfile and rebuild; the version change is
re-verified against Apache's SHA-512 at build time.

## Generated artifacts

A run against the bundled smoke-test plan produces:

- `reports/jmeter/smoke-test.jtl` — raw sample results (CSV/XML depending on
  `jmeter.save.saveservice.output_format`; default is XML for `-l`)
- `logs/jmeter/jmeter.log` — JMeter's own log for the run

Future runner-driven executions will additionally populate
`data/jmeter/artifacts/` once that layer exists.

## Sample test plan

[`docker/jmeter/test-plans/smoke-test.jmx`](../../docker/jmeter/test-plans/smoke-test.jmx)
is intentionally minimal and network-free: one thread, one loop, a Debug
Sampler (a built-in JMeter element that always succeeds and needs no
network), and a result collector. It exists purely to verify the container
can load and execute a test plan in non-GUI mode — it is not a real
performance test. Real HTTP/API test plans arrive with the Service/Runner
implementation.

## Network notes

The JMeter tarball is downloaded from Apache at image-build time. Some
networks block `archive.apache.org` (observed as `curl: (7) Connection
refused` on port 443). The build mitigates this by trying the Fastly-fronted
`dlcdn.apache.org` **first** (usually reachable and faster), then falling back
to the archive.

If **both** Apache hosts are blocked on your network, the build can't fetch
JMeter. In that case, either build on a network that permits the CDN, point
the download at an internal mirror, or pre-download `apache-jmeter-5.6.3.tgz`
and `COPY` it into the image instead of `curl`-ing it.

## Verifying this setup

Authored and statically validated in a sandbox with **no Docker daemon** and
Apache mirrors **network-blocked**, so `docker build` / `docker run` could not
be executed there. What *was* verified statically:

- `smoke-test.jmx` is well-formed XML with the expected elements
  (`ThreadGroup`, `DebugSampler`, `ResultCollector`) — Python `xml.dom.minidom`.
- `docker-compose.yml` parses and the `jmeter` service has the expected
  `profiles`, `volumes`, and `command` — PyYAML.
- The Dockerfile's multi-line `RUN` shell block passes `bash -n`.
- JMeter 5.6.3 confirmed current via the live
  [Apache JMeter changes page](https://jmeter.apache.org/changes.html).

**On a machine with Docker and CDN access**, finish verification:

```bash
cd mcp-server
docker compose build jmeter
docker compose --profile jmeter up jmeter
echo "exit code: $?"
ls -la reports/jmeter/ logs/jmeter/
```

Expect exit code `0`, a non-empty `reports/jmeter/smoke-test.jtl`, and a
`Tidying up ... @ ...` line near the end of `logs/jmeter/jmeter.log` (JMeter's
normal non-GUI shutdown message).

## Where things live (for contributors)

Placeholder packages only exist today — no logic — following the layout
[`standards/architecture/backend-layering.md`](../../../.ai/standards/architecture/backend-layering.md)
R3 mandates for every tool integration (the same standard explicitly calls
out *"a JMeter client dropped in `helpers/` instead of
`integrations/jmeter/`"* as the anti-pattern it exists to prevent):

- Request models (future): `app/schemas/tools/jmeter/`
- Service, orchestrates through the Runner only (future): `app/services/tools/jmeter/`
- Runner — builds CLI args, launches the `jmeter` subprocess/container,
  captures stdout/stderr, handles timeout + termination (future):
  `app/integrations/jmeter/`
- MCP router (future, not part of this phase): `app/routers/mcp/jmeter_router.py`

None of the above are implemented in this change — this task was
infrastructure setup only.
