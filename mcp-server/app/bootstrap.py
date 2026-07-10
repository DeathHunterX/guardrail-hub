"""In-process composition root for the Operation -> Notification flow.

Assembles the working pipeline entirely in-process (no HTTP, no background
workers):

    OperationService
        -> EventPublisher (InProcessEventDispatcher)
        -> EventNotificationSubscriber -> NotificationService
        -> SlackNotificationChannel

This is application assembly, kept separate from ``main.py`` because the flow is
in-process and has no HTTP surface. Dependencies are injected so the flow is
fully testable; a production entry point can call :func:`build_notification_flow`
with settings and the real DAO when one exists.
"""

from dataclasses import dataclass
from typing import Optional

from app.core.events.dispatcher import InProcessEventDispatcher
from app.dao.base import BaseOperationDAO
from app.integrations.chat.slack.channel_adapter import (
    SlackNotificationChannel,
    Transport,
)
from app.services.notification.event_subscriber import EventNotificationSubscriber
from app.services.notification.notification_service import NotificationService
from app.services.operations.operation_service import (
    EVENT_OPERATION_COMPLETED,
    EVENT_OPERATION_CREATED,
    OperationService,
)

SLACK_CHANNEL_NAME = "slack"

# Which operation events notify Slack, and the message each renders.
OPERATION_NOTIFICATION_TEMPLATES = {
    EVENT_OPERATION_CREATED: "Operation {operation_id} created.",
    EVENT_OPERATION_COMPLETED: "Operation {operation_id} completed.",
}


@dataclass
class NotificationFlow:
    """The assembled in-process flow. ``operation_service`` is the entry point."""

    operation_service: OperationService
    notification_service: NotificationService
    dispatcher: InProcessEventDispatcher


def build_notification_flow(
    *,
    dao: BaseOperationDAO,
    slack_token: str,
    destination: str,
    slack_transport: Optional[Transport] = None,
) -> NotificationFlow:
    """Wire the Operation -> Notification -> Slack flow and return it.

    Args:
        dao: Persistence backend for operations (existing ``BaseOperationDAO``).
        slack_token: Slack bot token for the Slack channel adapter.
        destination: Slack channel id notifications are delivered to.
        slack_transport: Optional HTTP transport for the Slack adapter; inject a
            fake in tests to avoid the network.

    Returns:
        The assembled :class:`NotificationFlow`.
    """
    dispatcher = InProcessEventDispatcher()

    slack = SlackNotificationChannel(slack_token, transport=slack_transport)
    notification_service = NotificationService([slack])

    subscriber = EventNotificationSubscriber(
        notification_service,
        channel=SLACK_CHANNEL_NAME,
        destination=destination,
        templates=OPERATION_NOTIFICATION_TEMPLATES,
    )
    for event_name in subscriber.event_names:
        dispatcher.subscribe(event_name, subscriber.handle)

    operation_service = OperationService(dao, dispatcher)
    return NotificationFlow(
        operation_service=operation_service,
        notification_service=notification_service,
        dispatcher=dispatcher,
    )


def build_platform_reporter(config=None, *, logger=None, slack_transport=None):
    """Build a PlatformReporter from settings.

    Reuses the existing NotificationService + SlackNotificationChannel + logger.
    When Slack is disabled, the reporter logs only (notification_service=None);
    lifecycle events are still fully logged.

    Args:
        config: Settings object; defaults to ``app.core.config.settings`` (lazy).
        logger: Logger to use; defaults to ``MCPLogger("platform")``.
        slack_transport: Optional Slack HTTP transport (tests).

    Returns:
        A ready ``PlatformReporter``.
    """
    if config is None:
        from app.core.config import settings as config
    if logger is None:
        from app.core.mcp_logger import MCPLogger

        logger = MCPLogger("platform")

    from app.services.platform.platform_reporter import PlatformReporter

    notification_service = None
    destination = None
    if config.slack_enabled:
        from app.integrations.chat.slack.channel_adapter import SlackNotificationChannel
        from app.services.notification.notification_service import NotificationService

        slack = SlackNotificationChannel(config.slack_bot_token, transport=slack_transport)
        notification_service = NotificationService([slack])
        destination = config.slack_default_channel

    return PlatformReporter(
        logger, notification_service=notification_service, destination=destination
    )


def build_zap_evaluation_service(operation_service, *, scan_runner=None):
    """Wire the OWASP ZAP evaluation flow onto an existing OperationService.

    Reuses the given ``OperationService`` (and therefore its dispatcher /
    notification pipeline). The scan runner defaults to the synchronous
    ``ZapScanRunner`` over the existing ZapClient; inject a fake in tests.

    Args:
        operation_service: The lifecycle service the evaluation drives.
        scan_runner: Optional synchronous scan callable. Defaults to
            ``ZapScanRunner()`` (imported lazily so this module does not require
            the zaproxy SDK).

    Returns:
        A ready ``EvaluationService``.
    """
    from app.services.evaluations.evaluation_service import EvaluationService

    if scan_runner is None:
        from app.services.evaluations.zap_scan_runner import ZapScanRunner

        scan_runner = ZapScanRunner()
    return EvaluationService(operation_service, scan_runner)


def build_notification_flow_from_settings(
    *,
    dao: BaseOperationDAO,
    config=None,
    slack_transport: Optional[Transport] = None,
) -> NotificationFlow:
    """Assemble the flow from the Settings layer (production wiring).

    The Slack channel is registered and operation events are subscribed **only
    when ``SLACK_ENABLED`` is true**. When disabled, operations still run and
    publish events, but no channel is registered and nothing subscribes, so no
    notifications are delivered.

    Args:
        dao: Persistence backend (existing ``BaseOperationDAO``).
        config: Settings object to read; defaults to ``app.core.config.settings``.
            Imported lazily so importing this module does not require loading
            settings (and injectable in tests).
        slack_transport: Optional HTTP transport for the Slack adapter (tests).

    Returns:
        The assembled :class:`NotificationFlow`.
    """
    if config is None:
        from app.core.config import settings as config

    dispatcher = InProcessEventDispatcher()

    channels = []
    if config.slack_enabled:
        channels.append(
            SlackNotificationChannel(config.slack_bot_token, transport=slack_transport)
        )
    notification_service = NotificationService(channels)

    if config.slack_enabled:
        subscriber = EventNotificationSubscriber(
            notification_service,
            channel=SLACK_CHANNEL_NAME,
            destination=config.slack_default_channel,
            templates=OPERATION_NOTIFICATION_TEMPLATES,
        )
        for event_name in subscriber.event_names:
            dispatcher.subscribe(event_name, subscriber.handle)

    operation_service = OperationService(dao, dispatcher)
    return NotificationFlow(
        operation_service=operation_service,
        notification_service=notification_service,
        dispatcher=dispatcher,
    )


def build_zap_dispatcher(*, dao: BaseOperationDAO, config=None):
    """Assemble the ZAP queue dispatcher (background worker-pool dispatch).

    Wires the process-wide Pool Manager singletons
    (``app.integrations.owasp_zap.runtime``) to *dao* and the
    ``ZapApiScanService`` singleton. The returned dispatcher is not started —
    the caller (``app/core/startup.py``) is responsible for
    ``.start()``/``.stop()`` as part of the app lifespan, matching this
    module's existing "assemble here, run there" split.

    Args:
        dao: The persistence backend for operations — required, since a
            dispatcher with nowhere to read the queue from cannot do
            anything. Callers should only invoke this when
            ``DATABASE_PROVIDER`` is not ``NONE``.
        config: Settings object; defaults to ``app.core.config.settings``.

    Returns:
        A ready, unstarted ``OwaspZapDispatcher``.
    """
    if config is None:
        from app.core.config import settings as config  # noqa: PLC0415

    from app.integrations.owasp_zap.runtime import pool_manager  # noqa: PLC0415
    from app.services.tools.owasp_zap.api_scanner import ZapApiScanService  # noqa: PLC0415
    from app.services.tools.owasp_zap.dispatcher import OwaspZapDispatcher  # noqa: PLC0415

    return OwaspZapDispatcher(
        operation_dao=dao,
        pool_manager=pool_manager,
        scan_service=ZapApiScanService(),
        queue_poll_interval_seconds=config.zap_queue_poll_interval_seconds,
        heartbeat_sweep_interval_seconds=config.zap_worker_heartbeat_sweep_interval_seconds,
        heartbeat_timeout_seconds=config.zap_worker_heartbeat_timeout_seconds,
    )
