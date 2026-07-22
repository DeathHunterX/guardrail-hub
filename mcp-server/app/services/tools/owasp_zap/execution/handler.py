"""The generic execution contract every ZAP tool implements.

Two units live here:

* :class:`ZapOperationHandler` — the Strategy interface that actually runs one
  operation. It is handed a neutral :class:`ExecutionContext` (ADR-0009 H1): a
  tool-owned ``ZapWorkerContext`` for worker-bound strategies, or the empty
  base for orchestration strategies.
* :class:`ZapOperation` — the registry entry that bundles the FOUR things a tool
  owns: its request **schema**, request **serialization** into metadata,
  request **deserialization** from metadata, and its execution **handler** (plus
  the operation type and execution strategy that classify it).

The Dispatcher only ever touches :class:`ZapOperation`. It never imports a
concrete request model, so adding a tool is purely a registration concern.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from app.services.tools.owasp_zap.execution.execution_context import ExecutionContext
from app.services.tools.owasp_zap.execution.execution_strategy import ExecutionStrategy
from app.services.tools.owasp_zap.execution.operation_type import ZapOperationType


@runtime_checkable
class ZapOperationHandler(Protocol):
    """Strategy that executes one operation type.

    Implementations do NO scheduling. For a worker-bound strategy the handler
    receives a ``ZapWorkerContext`` carrying the already-assigned worker and
    runs the scan on it, releasing it when done (exactly as the legacy
    ``run_assigned_scan`` did). For an orchestration strategy the ``context`` is
    the empty :class:`ExecutionContext` base and the handler spawns / aggregates
    child operations without touching the worker pool.
    """

    def execute(
        self,
        operation_id: str,
        request: Any,
        context: ExecutionContext,
    ) -> None:
        """Execute *operation_id*. See class docstring for the ``context`` contract."""


@dataclass(frozen=True)
class ZapOperation:
    """A fully-described, registrable ZAP tool.

    The single façade the Dispatcher works with. Bundles the four
    responsibilities a tool owns so that none of them leak into the Dispatcher:
    ``request_model`` (schema), :meth:`serialize_request` (metadata
    serialization), :meth:`deserialize_request` (metadata deserialization) and
    ``handler`` (execution).
    """

    operation_type: ZapOperationType
    execution_strategy: ExecutionStrategy
    request_model: type[BaseModel]
    handler: ZapOperationHandler

    def serialize_request(self, request: BaseModel) -> dict:
        """Shape a typed request into the ``metadata["request"]`` payload.

        Used by a tool's submit path so serialization lives with the operation
        definition rather than being reinvented per service. Mirrors the
        existing ``model_dump(mode="json", by_alias=True)`` shape so persisted
        rows stay byte-compatible with the current format.
        """
        return request.model_dump(mode="json", by_alias=True)

    def deserialize_request(self, metadata: dict) -> BaseModel:
        """Rebuild the typed request from a persisted queue row.

        Raises (``KeyError`` / ``pydantic.ValidationError``) on malformed or
        legacy-incompatible metadata; the Dispatcher treats that as an
        unrecoverable operation — marks it FAILED and releases any worker —
        exactly as it does today for unusable metadata.
        """
        return self.request_model.model_validate(metadata["request"])
