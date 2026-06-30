from abc import ABC, abstractmethod
from typing import Any, Optional

from app.schemas.internal.operation import OperationRecord


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
            status:       New status value (use :class:`~app.schemas.tools.owasp_zap.common.OperationStatus` members).
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
