"""JMeter test-run service — the JMeter analogue of the OWASP ZAP tool services.

Mirrors ``ZapApiSuiteService``: a singleton submit adapter that validates a
request and persists a ``QUEUED`` operation, then returns immediately. The
generic background dispatcher assigns the operation to a warm worker, which pulls
the plan and runs ``jmeter -n``. This service never executes anything itself.

JMeter-first: a tester passes the path to an existing ``.jmx`` file (as with
``jmeter -n -t <file>``). The file is read, validated (JMX whitelist), stored, and
enqueued. Internal engine concepts (stored plans, the queue, operation metadata,
internal ids) stay internal; the plan is stored under the operation id — the key
the worker pulls by — before the operation is enqueued.
"""

import uuid
from pathlib import Path
from threading import Lock
from typing import Optional

# Constants
from app.constants.batch import BatchType

# Core
from app.core.events.dispatcher import InProcessEventDispatcher
from app.core.mcp_logger import MCPLogger

# DAO
from app.dao.operation_dao import get_operation_dao

# Integrations
from app.integrations.jmeter.plan_validator import JmxPlanValidator

# Schemas
from app.schemas.performance.operation_type import PerformanceOperationType
from app.schemas.tools.jmeter.run_test import RunJmeterTestRequest

# Service
from app.services.operations.operation_service import OperationService
from app.services.performance.stores import FilesystemPlanStore

# Server-owned validated-plan store base (mirrors the coordinator's base, so a
# stored plan resolves by operation id at pull time — data/jmeter/plans).
_PLAN_STORE_BASE = Path("data/jmeter/plans")


class JmxFileNotFoundError(FileNotFoundError):
    """The referenced ``.jmx`` path does not exist or is not a regular file."""

    def __init__(self, jmx_file: str) -> None:
        super().__init__(f"JMX file not found or not a regular file: {jmx_file}")
        self.jmx_file = jmx_file


class JmeterRunService:
    """Singleton service that runs existing Apache JMeter ``.jmx`` test plans."""

    _instance: Optional["JmeterRunService"] = None
    _instance_lock: Lock = Lock()

    def __new__(cls, *args, **kwargs) -> "JmeterRunService":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        operation_service: Optional[OperationService] = None,
        validator: Optional[JmxPlanValidator] = None,
        plan_store: Optional[FilesystemPlanStore] = None,
    ) -> None:
        # Singleton: allow injection of the shared OperationService (and, in
        # tests, the validator/plan store) even if a prior no-arg construction ran.
        if getattr(self, "_initialized", False):
            if operation_service is not None:
                self.operation_service = operation_service
            if validator is not None:
                self.validator = validator
            if plan_store is not None:
                self.plan_store = plan_store
            return

        self.app_logger = MCPLogger("JmeterRunService")
        self.validator = validator or JmxPlanValidator()
        self.plan_store = plan_store or FilesystemPlanStore(_PLAN_STORE_BASE)
        self.operation_dao = get_operation_dao()
        self.operation_service = operation_service or OperationService(
            self.operation_dao, InProcessEventDispatcher()
        )
        self._initialized = True

    # ------------------------------------------------------------------
    # Submit (persist QUEUED)
    # ------------------------------------------------------------------

    def run(self, request: RunJmeterTestRequest) -> dict:
        """Validate the ``.jmx`` file in *request* and persist a ``QUEUED`` operation.

        Returns a dict with ``operation_id``, ``status``, and a status-check
        message. Raises :class:`JmxFileNotFoundError` if the file is missing, or
        the validator's ``JmxValidationError`` if the plan is unsafe — nothing is
        enqueued in either case.
        """
        path = Path(request.jmx_file)
        if not path.is_file():
            raise JmxFileNotFoundError(request.jmx_file)

        plan = path.read_bytes()
        # Validate before anything is stored or queued: an unsafe plan never runs.
        self.validator.validate(plan)

        op_id = str(uuid.uuid4())
        # Store the plan under the operation id FIRST (the worker's pull key), so
        # it is on disk before the operation becomes visible in the queue.
        self.plan_store.put(op_id, plan, request.timeout_seconds)
        self.operation_service.create(
            batch_type=BatchType.PERFORMANCE_TEST,
            operation_id=op_id,
            metadata={
                "operation_type": PerformanceOperationType.PERFORMANCE_TEST.value,
                "jmx_file": str(path),
            },
        )

        self.app_logger.info(f"Queued JMeter test with operation_id: {op_id}")

        return {
            "operation_id": op_id,
            "status": "queued",
            "message": (
                f"JMeter test queued with operation_id: {op_id}. "
                "It will start as soon as a worker is available."
            ),
        }
