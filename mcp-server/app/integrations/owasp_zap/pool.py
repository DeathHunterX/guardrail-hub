import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from zapv2 import ZAPv2

from app.core.config import settings
from app.core.mcp_logger import MCPLogger
from app.integrations.owasp_zap.client import ZapClient
from app.schemas.tools.owasp_zap.common import OperationStatus


class OwaspZapPool:
    """
    In-memory registry of ZAP client instances, one per Docker container.

    Each ZAP container is a separate Docker service reachable via the internal
    Docker network by its service name — ports are NEVER exposed to the host.

    Naming convention
    -----------------
    Given ``zap_container_name_prefix = "zap"`` and
    ``zap_amount_of_containers = 3``, the pool manages:

        zap-1  →  http://zap-1:8080   (internal Docker URL)
        zap-2  →  http://zap-2:8080
        zap-3  →  http://zap-3:8080

    The container name ``zap-{i}`` must match the Docker Compose service name
    exactly so that DNS resolution works inside the shared network.

    Thread safety
    -------------
    ``acquire_node`` / ``update_node`` / ``get_ready_node`` are guarded by a
    single ``threading.Lock``.  Each ``ZapClient`` is itself thread-safe.
    """

    def __init__(self, number: int = 1) -> None:
        prefix = settings.zap_container_name_prefix
        port = settings.zap_api_port

        self._pairs: Dict[str, dict] = {
            f"{prefix}-{i}": {
                "operation_id": None,
                "client": ZapClient(
                    api_url=f"http://{prefix}-{i}:{port}",
                    api_key=settings.zap_api_key,
                ),
            }
            for i in range(1, number + 1)
        }

        self.state_logger = MCPLogger("OwaspZapPool")
        self._lock = threading.Lock()

    # ── Node lifecycle ────────────────────────────────────────

    def acquire_node(self, operation_id: str) -> Optional[str]:
        """
        Atomically claim the first idle node for *operation_id*.

        Returns:
            The container name (e.g. ``"zap-1"``) if a node was claimed;
            ``None`` when all nodes are busy.
        """
        with self._lock:
            for container_name, info in self._pairs.items():
                if info["operation_id"] is None:
                    info["operation_id"] = operation_id
                    return container_name

            self.state_logger.warning(
                f"No idle node found for operation_id: {operation_id}, "
                "all nodes are busy, waiting for a node to become idle..."
            )
            return None

    def get_ready_node(self) -> Optional[str]:
        """Return the name of the first idle container, or ``None`` if all are busy."""
        with self._lock:
            for container_name, info in self._pairs.items():
                if info["operation_id"] is None:
                    return container_name

            self.state_logger.warning(
                "No idle node found, all nodes are busy, "
                "waiting for a node to become idle..."
            )
            return None

    def update_node(self, container_name: str, operation_id: Optional[str]) -> None:
        """
        Assign or release an operation on a node.

        Args:
            container_name: Docker service name, e.g. ``"zap-1"``.
            operation_id:   Operation to assign, or ``None`` to release the
                            node back to idle.

        Raises:
            KeyError: if *container_name* is not registered in the pool.
        """
        with self._lock:
            if container_name not in self._pairs:
                raise KeyError(
                    f"ZAP container '{container_name}' not found in pool"
                )
            self._pairs[container_name]["operation_id"] = operation_id

    # ── Client access ─────────────────────────────────────────
    def get_zap_client(self, container_name: str) -> ZapClient:
        """
        Return the ``ZapClient`` bound to *container_name*.

        Raises:
            KeyError: if *container_name* is not registered in the pool.
        """
        try:
            return self._pairs[container_name]["client"]
        except KeyError as exc:
            raise KeyError(
                f"ZAP container '{container_name}' not found in pool"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Error getting ZAP client for container '{container_name}'"
            ) from exc

    def is_slot_available(self) -> bool:
        """Return True if a slot is available, False otherwise."""
        return self.get_ready_node() is not None

    def list_slots(self) -> List[str]:
        """Return a list of all slots even if they are busy."""
        with self._lock:
            return list(self._pairs.keys())

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Return the status of all slots."""
        with self._lock:
            return {"slots": {k: dict(v) for k, v in self._pairs.items()}}

    
    # ── Node management ─────────────────────────────────────────
    def book_zap_slot(self, operation_id: str, poll_seconds: float = 2.0) -> Tuple[str, ZapClient, ZAPv2]:
        """Book a ZAP slot for the given operation_id.

        Returns a ``(container_name, zap_client, zap_api)`` tuple where:

        * ``zap_client`` — :class:`ZapClient` wrapper methods
        * ``zap_api``    — raw ``ZAPv2`` SDK object
        """
        while True:
            # Will handle it later when we have set up database in local (postgresql) or remote (dynamodb)
            # Exit early if a stop call already marked this operation as cancelled
            # try:
            #     op = self.operation_dao.get_operation(operation_id)
            #     if isinstance(op, dict) and op.get("status") == OperationStatus.CANCELLED:
            #         raise ValueError(
            #             f"Operation {operation_id} was cancelled while waiting for a ZAP slot"
            #         )
            # except ValueError:
            #     raise
            # except Exception:
            #     pass  # transient DB error; keep polling for a slot

            zap_container = self.acquire_node(operation_id)
            if zap_container is not None:
                zap_client = self.get_zap_client(zap_container)
                return zap_container, zap_client, zap_client.zap_api

            time.sleep(poll_seconds)  # Wait for a slot to become available

    def release_zap_slot(self, zap_container: str, operation_id: str) -> None:
        """Release a ZAP slot for the given operation_id."""
        try:
            # Ensure atomic read + update
            if operation_id is not None:
                status = self.get_status()
                # Check current owner to avoid releasing someone else's slot
                current_owner = (
                    status["slots"].get(zap_container, {}).get("operation_id")
                )

                if current_owner != operation_id:
                    # Skip if slot was already reassigned
                    self.state_logger.debug(
                        "release_zap_slot: skipped [%s] — owned by %s, not %s",
                        zap_container,
                        current_owner,
                        operation_id,
                    )
                    return

            # Release slot (make it available)
            self.update_node(zap_container, None)

        except Exception:
            pass  # Fail-safe: avoid breaking worker flow