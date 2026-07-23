from abc import ABC, abstractmethod
from typing import Any, Collection, Optional

from app.dao.operation_record import OperationRecord


def scope_queued_by_type(
    records: list[OperationRecord], types: Optional[Collection[str]]
) -> list[OperationRecord]:
    """Filter *records* to those whose ``metadata['operation_type']`` is in *types*.

    The one place the type-scoped queued read is implemented (ADR-0010 §4.12), so
    every DAO backend shares identical scoping semantics. ``types=None`` returns
    *records* unchanged (the original unscoped behaviour). Operations with no
    ``operation_type`` in metadata are only returned by the unscoped read — a
    scoped caller asks for explicit types.
    """
    if types is None:
        return records
    allowed = frozenset(types)
    return [r for r in records if r.metadata.get("operation_type") in allowed]


class BaseOperationDAO(ABC):
    """
    Common interface that every operation-persistence backend must implement.

    Concrete subclasses
    -------------------
    * :class:`app.dao.postgres.operation_dao.PostgresOperationDAO`  — local PostgreSQL
    * :class:`app.dao.dynamodb.operation_dao.DynamoDBOperationDAO` — remote DynamoDB
    """

    @abstractmethod
    def create_operation(
        self,
        op_id: str,
        status: str,
        metadata: dict[str, Any],
        batch_type: str,
        log_path: Optional[str] = None,
    ) -> None:
        """
        Persist a new operation record keyed on *op_id*.

        Args:
            op_id:      Unique operation identifier (primary key).
            status:     Initial status value.
            metadata:   Arbitrary key-value context (targets, config, etc.).
            batch_type: Category / tool type that produced this operation.
            log_path:   Optional filesystem path to the operation log file.

        Raises:
            Exception: Any driver-level error from the underlying backend.
        """

    @abstractmethod
    def get_operation(self, operation_id: str) -> Optional[OperationRecord]:
        """
        Retrieve a single operation by its primary key.

        Args:
            operation_id: The unique operation identifier.

        Returns:
            The :class:`OperationRecord` if found, otherwise ``None``.

        Raises:
            Exception: Any driver-level error from the underlying backend.
        """

    @abstractmethod
    def update_operation_status(
        self,
        operation_id: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None,
        clear_error: bool = False,
    ) -> None:
        """
        Partially update *status*, *result*, and *error* for an existing operation.

        ``updated_at`` is always refreshed to the current UTC time.

        Args:
            operation_id: The unique operation identifier.
            status:       New status value (use :class:`~app.schemas.tools.owasp_zap.common.OperationPhase` members).
            result:       Optional result payload to store.
            error:        Optional error message to store (pass ``None`` to clear).
            clear_error:  When ``True``, removes the error field entirely from the record
                          (DynamoDB ``REMOVE``, PostgreSQL ``SET error = NULL``).

        Raises:
            Exception: Any driver-level error from the underlying backend.
        """

    @abstractmethod
    def get_all(self) -> list[OperationRecord]:
        """
        Return every operation record (without the ``result`` field).

        Returns:
            A list of :class:`OperationRecord` objects (may be empty).

        Raises:
            Exception: Any driver-level error from the underlying backend.
        """

    @abstractmethod
    def get_by_type(self, batch_type: str) -> list[OperationRecord]:
        """
        Return all operation records whose ``batch_type`` matches *batch_type*.

        Args:
            batch_type: The batch type to filter by.

        Returns:
            A (possibly empty) list of matching :class:`OperationRecord` objects.

        Raises:
            Exception: Any driver-level error from the underlying backend.
        """

    @abstractmethod
    def get_by_status(self, *statuses: str) -> list[OperationRecord]:
        """
        Return all operation records whose ``status`` is one of *statuses*.

        Passing no arguments is equivalent to calling :meth:`get_all`.

        Args:
            *statuses: One or more status strings to filter by.

        Returns:
            A (possibly empty) list of matching :class:`OperationRecord` objects.

        Raises:
            Exception: Any driver-level error from the underlying backend.
        """

    # ── Queue (the Operations table *is* the queue — no in-memory queue) ──────

    def get_queued_operations(
        self, types: Optional[Collection[str]] = None
    ) -> list[OperationRecord]:
        """
        Return ``QUEUED`` operations, oldest first (FIFO by ``created_at``).

        This is what a Pool Manager / dispatcher polls instead of maintaining an
        in-memory waiting queue — queued operations, and therefore pending
        requests, survive a server restart because they live here.

        When *types* is given, only operations whose
        ``metadata['operation_type']`` is in *types* are returned — the
        **type-scoped** read that lets multiple engines' dispatchers share one
        queue safely (ADR-0010 §4.12). ``types=None`` is the original **unscoped**
        read, preserved unchanged for backward compatibility.

        The default implementation is a correct but not necessarily
        efficient fallback built on :meth:`get_by_status`; backends should
        override it with a native ordered query (e.g. ``ORDER BY created_at
        ASC`` in PostgreSQL) when that's cheaper than sorting in Python.

        Raises:
            Exception: Any driver-level error from the underlying backend.
        """
        from app.domain.lifecycle import OperationPhase  # noqa: PLC0415

        records = self.get_by_status(OperationPhase.QUEUED)
        return scope_queued_by_type(sorted(records, key=lambda r: r.created_at), types)

    # ── Startup schema readiness ────────────────────────────────────────────

    def initialize_schema(self) -> None:
        """
        Verify (and, where applicable, apply) the schema this backend needs
        before the server accepts requests.

        Part of the startup sequence: Database Ready -> Run Migrations ->
        Verify required tables -> Initialize services -> Start HTTP Server ->
        Accept Requests. Must raise on any failure so startup aborts with a
        non-zero exit code rather than serving requests against a missing or
        stale schema.

        The default implementation is a no-op (e.g. an in-memory test fake
        has no schema to verify). Real backends
        (:class:`~app.dao.postgres.operation_dao.PostgresOperationDAO`,
        :class:`~app.dao.dynamodb.operation_dao.DynamoDBOperationDAO`)
        override this.

        Raises:
            Exception: If the schema cannot be verified or brought up to date.
        """
        return None
