"""Process-wide Performance worker-pool singleton wiring (composition root).

The Performance analogue of ``app/integrations/owasp_zap/runtime.py`` — but this
module deliberately holds **only the settings-free** singleton: the Worker
Registry. It is constructed exactly once per process and shared by everything
that touches the pool (the worker-facing router's coordinator and the queue
dispatcher import the *same* instance from here — Gate A), so the router can
never register a worker into a registry the dispatcher never looks at.

It is **not** named ``runtime.py`` (ADR-0010 §4.10): "Runtime" is the worker-side
lifecycle manager; this is pool wiring, owned by the composition root. It reads
no ``Settings`` (Gate E). The Scheduler and Pool Manager depend on a
settings-derived fitness (``min_compatible_version``, §4.8/INV11), so they are
built in ``bootstrap`` (which may read Settings), not here.
"""

from app.integrations.performance.registry import PerformanceWorkerRegistry

# The one process-wide worker registry. Shared by the coordinator and dispatcher.
registry = PerformanceWorkerRegistry()
