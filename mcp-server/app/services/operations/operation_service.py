"""Operation application service.

Owns the Operation lifecycle: create an operation, transition its status, and
publish a domain event on every transition via the EventPublisher port.

Design notes:
- Persistence goes through the existing ``BaseOperationDAO`` abstraction — no new
  repository port is introduced and the DAO's provider selection is unchanged.
- Event delivery is decoupled behind the ``EventPublisher`` port; at MVP the
  in-process dispatcher implements it.
- This service is deliberately unaware of OWASP ZAP, notifications, and HTTP.
  Those integrations are wired in later slices. It keeps the existing domain
  vocabulary (Operation, batch_type, OperationStatus).
"""

from typing import TYPE_CHECKING, Any, Callable, Optional
from uuid import uuid4

from app.core.ports.event_publisher import DomainEvent, EventPublisher
from app.schemas.tools.owasp_zap.common import OperationStatus

if TYPE_CHECKING:  # keep runtime imports light (no psycopg2/boto3 pulled in here)
    from app.dao.base import BaseOperationDAO
    from app.schemas.internal.operation import OperationRecord

# Domain event names emitted across the operation lifecycle.
EVENT_OPERATION_CREATED = "operation.created"
EVENT_OPERATION_STARTED = "operation.started"
EVENT_OPERATION_COMPLETED = "operation.completed"
EVENT_OPERATION_FAILED = "operation.failed"
EVENT_OPERATION_CANCELLED = "operation.cancelled"


def _default_id_suffix() -> str:
    """Unique suffix used to build an operation id (overridable in tests)."""
    return uuid4().hex


class OperationService:
    """Creates operations and drives their lifecycle, publishing an event per step."""

    def __init__(
        self,
        dao: "BaseOperationDAO",
        publisher: EventPublisher,
        id_suffix: Callable[[], str] = _default_id_suffix,
    ) -> None:
        """
        Args:
            dao: The persistence abstraction (existing ``BaseOperationDAO``).
            publisher: The event-publishing port; the in-process dispatcher at MVP.
            id_suffix: Factory for the unique part of an operation id. Injectable
                so tests can produce deterministic ids.
        """
        self._dao = dao
        self._publisher = publisher
        self._id_suffix = id_suffix

    def create(
        self,
        batch_type: str,
        metadata: Optional[dict[str, Any]] = None,
        log_path: Optional[str] = None,
    ) -> str:
        """Create a new QUEUED operation, persist it, and publish ``operation.created``.

        The operation is persisted with ``status=QUEUED`` — this *is* the work
        queue entry. A Pool Manager (or equivalent dispatcher) later fetches
        queued operations ordered by creation time and assigns them to a
        registered worker; nothing is held in an in-memory queue.

        Args:
            batch_type: Category / tool type for this operation (see ``BatchType``).
            metadata: Arbitrary creation-time context (targets, config, ...).
            log_path: Optional path to the operation's log file.

        Returns:
            The newly created operation id (``"<batch_type>:<suffix>"``).
        """
        operation_id = f"{batch_type}:{self._id_suffix()}"
        self._dao.create_operation(
            op_id=operation_id,
            status=OperationStatus.QUEUED,
            metadata=metadata or {},
            batch_type=batch_type,
            log_path=log_path,
        )
        self._publish(EVENT_OPERATION_CREATED, operation_id, batch_type=batch_type)
        return operation_id

    def start(self, operation_id: str) -> None:
        """Transition an operation to RUNNING and publish ``operation.started``."""
        self._dao.update_operation_status(
            operation_id=operation_id, status=OperationStatus.RUNNING
        )
        self._publish(EVENT_OPERATION_STARTED, operation_id)

    def complete(self, operation_id: str, result: Any = None) -> None:
        """Transition an operation to COMPLETED and publish ``operation.completed``."""
        self._dao.update_operation_status(
            operation_id=operation_id,
            status=OperationStatus.COMPLETED,
            result=result,
        )
        self._publish(EVENT_OPERATION_COMPLETED, operation_id)

    def fail(self, operation_id: str, error: str) -> None:
        """Transition an operation to FAILED and publish ``operation.failed``."""
        self._dao.update_operation_status(
            operation_id=operation_id,
            status=OperationStatus.FAILED,
            error=error,
        )
        self._publish(EVENT_OPERATION_FAILED, operation_id, error=error)

    def cancel(self, operation_id: str) -> None:
        """Transition an operation to CANCELLED and publish ``operation.cancelled``."""
        self._dao.update_operation_status(
            operation_id=operation_id, status=OperationStatus.CANCELLED
        )
        self._publish(EVENT_OPERATION_CANCELLED, operation_id)

    def get(self, operation_id: str) -> "Optional[OperationRecord]":
        """Return an operation by id, delegating to the DAO (or ``None``)."""
        return self._dao.get_operation(operation_id)

    def _publish(self, name: str, operation_id: str, **extra: Any) -> None:
        payload: dict[str, Any] = {"operation_id": operation_id}
        payload.update(extra)
        self._publisher.publish(DomainEvent(name=name, payload=payload))
