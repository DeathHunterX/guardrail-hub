"""Presentation-enrichment tests for OperationNotifier.

Verifies the notifier resolves a friendly title from batch_type (and remembers
it across the single edited message), derives a short reference, passes optional
presentation payload keys through to the card, and honours Debug Mode — all
without changing delivery/throttle behaviour.
"""

import unittest

from app.core.ports.event_publisher import DomainEvent
from app.core.ports.notification_channel import ChannelCapabilities, NotificationChannel
from app.services.notification.notification_service import NotificationService
from app.services.notification.operation_notifier import OperationNotifier
from app.services.notification.operation_progress import LifecyclePhase

LIFECYCLE = {
    "operation.created": LifecyclePhase.QUEUED,
    "operation.started": LifecyclePhase.RUNNING,
    "operation.completed": LifecyclePhase.COMPLETED,
    "operation.failed": LifecyclePhase.FAILED,
}
PROGRESS = frozenset({"operation.progress"})
TITLES = {"api_scan": "API Security Scan", "web_scan": "Website Security Scan"}


class CapturingChannel(NotificationChannel):
    def __init__(self, caps):
        self._caps = caps
        self.messages = []

    @property
    def name(self):
        return "chat"

    @property
    def capabilities(self):
        return self._caps

    def send(self, destination, message):
        self.messages.append(message)
        return f"ts-{len(self.messages)}"

    def update(self, destination, ref, message):
        self.messages.append(message)
        return ref


def _clock():
    return 0.0


def _notifier(channel, debug=False, context_resolver=None):
    return OperationNotifier(
        NotificationService([channel]),
        channel="chat",
        destination="C1",
        lifecycle_events=LIFECYCLE,
        progress_events=PROGRESS,
        titles=TITLES,
        debug=debug,
        clock=_clock,
        context_resolver=context_resolver,
    )


def _event(name, operation_id="api_scan:1d015005-4f", **payload):
    return DomainEvent(name=name, payload={"operation_id": operation_id, **payload})


class PresentationEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.channel = CapturingChannel(
            ChannelCapabilities(supports_message_update=True, supports_progress=True)
        )
        self.notifier = _notifier(self.channel)

    def test_title_persists_and_identifier_is_phase_appropriate(self):
        # Only the created event carries batch_type; later edits must still show
        # the resolved title. The short reference shows throughout; the full id
        # appears only on the completed card (for get-result).
        self.notifier.handle(_event("operation.created", batch_type="api_scan"))
        self.notifier.handle(_event("operation.progress", stage="active scan", progress=55))
        self.notifier.handle(_event("operation.completed"))

        for message in self.channel.messages:
            self.assertIn("API Security Scan", message)

        queued, running, completed = self.channel.messages
        self.assertIn("Operation #1D015005", queued)          # short ref by default
        self.assertNotIn("api_scan:1d015005-4f", queued)      # full id hidden
        self.assertNotIn("api_scan:1d015005-4f", running)     # full id hidden
        self.assertIn("Operation ID: api_scan:1d015005-4f", completed)  # full id on completion

    def test_completed_card_renders_findings_and_get_result_helper(self):
        self.notifier.handle(_event("operation.created", batch_type="api_scan"))
        self.notifier.handle(
            _event(
                "operation.completed",
                findings={
                    "critical": 0,
                    "high": 1,
                    "medium": 3,
                    "low": 8,
                    "informational": 12,
                },
            )
        )
        final = self.channel.messages[-1]
        self.assertIn(
            "Critical 0 · High 1 · Medium 3 · Low 8 · Info 12", final
        )
        self.assertIn("get-result", final)

    def test_default_hides_infrastructure(self):
        self.notifier.handle(_event("operation.created", batch_type="api_scan"))
        self.notifier.handle(_event("operation.progress", stage="spider", progress=25, worker_id="worker-9"))
        joined = "\n".join(self.channel.messages)
        self.assertIn("Discovering attack surface", joined)
        self.assertNotIn("worker-9", joined)
        self.assertNotIn("Debug", joined)

    def test_target_is_resolved_from_context_resolver(self):
        # The scan target is not in the event payload; the notifier pulls it from
        # the injected read-only resolver and shows it on every card.
        channel = CapturingChannel(
            ChannelCapabilities(supports_message_update=True, supports_progress=True)
        )
        notifier = _notifier(
            channel, context_resolver=lambda oid: {"target": "POST /api/auth/login"}
        )
        notifier.handle(_event("operation.created", batch_type="api_scan"))
        notifier.handle(_event("operation.progress", stage="active scan", progress=55))
        for message in channel.messages:
            self.assertIn("POST /api/auth/login", message)

    def test_report_link_from_resolver_appears_on_completed_card(self):
        # The report link lives in the persisted result; the notifier pulls it
        # from the resolver (no scan-execution coupling) and shows it once done.
        channel = CapturingChannel(
            ChannelCapabilities(supports_message_update=True, supports_progress=True)
        )
        notifier = _notifier(
            channel,
            context_resolver=lambda oid: {"report_link": "https://example/report/x"},
        )
        notifier.handle(_event("operation.created", batch_type="api_scan"))
        notifier.handle(_event("operation.completed", findings={"high": 1}))
        final = channel.messages[-1]
        self.assertIn("Report", final)
        self.assertIn("https://example/report/x", final)


class DebugModeNotifierTests(unittest.TestCase):
    def test_debug_mode_surfaces_worker_and_operation_id(self):
        channel = CapturingChannel(
            ChannelCapabilities(supports_message_update=True, supports_progress=True)
        )
        notifier = _notifier(channel, debug=True)

        notifier.handle(_event("operation.created", batch_type="api_scan"))
        notifier.handle(_event("operation.progress", stage="active scan", progress=55, worker_id="worker-9"))

        final = channel.messages[-1]
        self.assertIn("Debug", final)
        self.assertIn("worker-9", final)
        self.assertIn("api_scan:1d015005-4f", final)


if __name__ == "__main__":
    unittest.main()
