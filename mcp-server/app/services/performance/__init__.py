"""Performance Engine — engine-neutral capability package.

The application-side home of the Performance capability defined by
[ADR-0010](../../../../.ai/decisions/0010-performance-engine-capability.md) §4.1.
Everything here is **engine-neutral**: it speaks in plans, operations, policies,
artifacts, and workers — never in JMeter (or k6/Gatling) specifics. The single
concrete engine, JMeter, lives behind the seam in ``app/integrations/jmeter/``.

Subpackages (added as each Phase 1+ component lands):

- ``engine/``    — the replaceable-engine seam: ``PerformanceRunner`` protocol
                   + neutral ``ExecutionRequest`` / ``ExecutionResult`` /
                   ``ArtifactSet`` DTOs. One implementation today (JMeter);
                   no multi-engine framework (ADR-0010 §2.4 / D5).
- ``runtime/``   — the worker-side execution-lifecycle manager.
- ``policy/``    — execution-policy resolution.
- ``redaction/`` — artifact redaction.
- ``worker/``    — the long-lived warm-worker loop.
"""
