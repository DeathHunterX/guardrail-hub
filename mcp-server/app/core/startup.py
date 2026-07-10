"""
Application startup sequence.

Required order (never violated):

    1. Database Ready
    2. Run Migrations
    3. Verify required tables
    4. Initialize services
    5. Start HTTP Server
    6. Accept Requests

Steps 1-4 run here, inside the ASGI lifespan's startup phase, *before*
``yield`` in ``app/main.py``. Uvicorn does not start accepting connections
until lifespan startup completes, and aborts the whole process (non-zero
exit) if that phase raises — so "stop startup on migration failure, exit
non-zero" falls directly out of raising here rather than being a convention
someone has to remember to check.
"""

from typing import Optional

from app.core.mcp_logger import MCPLogger


class StartupError(RuntimeError):
    """Raised when the startup sequence cannot complete; must abort boot."""


def run_startup_sequence(settings) -> Optional[object]:
    """Run steps 1-4 of the startup sequence and start the ZAP queue dispatcher.

    Returns the running dispatcher (so the caller can stop it on shutdown), or
    ``None`` when ``DATABASE_PROVIDER=NONE`` — a supported "no persistence"
    deployment mode in which the ZAP queue simply has nothing to poll, but
    every other endpoint (health, etc.) still works.

    Raises:
        StartupError: If the database schema cannot be verified/migrated.
            Must be allowed to propagate out of the ASGI lifespan so the
            server aborts with a non-zero exit code — never start the API
            with an invalid database schema.
    """
    logger = MCPLogger("startup")

    if settings.database_provider == "NONE":
        logger.warning(
            "DATABASE_PROVIDER=NONE — operations are not persisted, so the ZAP "
            "queue dispatcher will not start. Endpoints that don't require "
            "persistence (health, etc.) are unaffected."
        )
        return None

    # 1. Database Ready / 2. Run Migrations / 3. Verify required tables
    from app.dao.operation_dao import get_operation_dao  # noqa: PLC0415

    try:
        dao = get_operation_dao()
        dao.initialize_schema()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Startup aborted — database schema not ready: %s", exc)
        raise StartupError(f"Database schema initialization failed: {exc}") from exc

    # 4. Initialize services (the ZAP worker-pool dispatcher).
    from app.bootstrap import build_zap_dispatcher  # noqa: PLC0415

    dispatcher = build_zap_dispatcher(dao=dao, config=settings)
    dispatcher.start()
    logger.info("Startup sequence complete — database ready, ZAP queue dispatcher running")
    return dispatcher
