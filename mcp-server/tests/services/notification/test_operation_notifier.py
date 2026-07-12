"""Unit tests for the capability-aware OperationNotifier.

Uses in-memory fake channels (no Slack, no network) to prove the two delivery
strategies: update-in-place for message-update channels, and new-message-per-
lifecycle-transition (progress skipped) for append-only fallback channels.
"""

import unittest

from app.core.ports.event_publisher import DomainEvent
from app.core.ports.notification_channel import ChannelCapabilities, NotificationChannel
from app.services.notification.notification_service import NotificationService
from app.services.notification.operation_notifier import OperationNotifier
from app.services.notification.operation_progress import LifecyclePhase

# Event-name -> phase map (mirrors the composition root, kept local to the test).
LIFECYCLE = {
    "operation.created": LifecyclePhase.QUEUED,
    "operation.started": LifecyclePhase.RUNNING,
    "operation.completed": LifecyclePhase.COMPLETED,
    "operation.failed": LifecyclePhase.FAILED,
    "operation.cancelled": LifecyclePhase.CANCELLED,
}
PROGRESS = frozenset({"operation.progress"})


class FakeChannel(NotificationChannel):
    def __init__(self, name, caps):
        self._name = name
        self._caps = caps
        self.sends = []
        self.updates = []
        self._counter = 0

    @property
    def name(self):
        return self._name

    @property
    def capabilities(self):
        return self._caps

    def send(self, destination, message):
        self._counter += 1
        ref = f"ts-{self._counter}"
        self.sends.append((destination, message, ref))
        return ref

    def update(self, destination, ref, message):
        self.updates.append((destination, ref, message))
        return ref


def _event(name, operation_id="api_scan:1", **payload):
    return DomainEvent(name=name, payload={"operation_id": operation_id, **payload})


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class UpdateChannelStrategyTests(unittest.TestCase):
    def setUp(self):
        self.channel = FakeChannel(
            "chat",
            ChannelCapabilities(
                supports_message_update=True, supports_progress=True
            ),
        )
        self.notifier = OperationNotifier(
            NotificationService([self.channel]),
            channel="chat",
            destination="C1",
            lifecycle_events=LIFECYCLE,
            progress_events=PROGRESS,
            clock=FakeClock(),
        )

    def test_single_message_updated_across_lifecycle(self):
        self.notifier.handle(_event("operation.created"))
        self.notifier.handle(_event("operation.started"))
        self.notifier.handle(_event("operation.completed"))

        # One initial send (QUEUED), then edits for RUNNING + COMPLETED.
        self.assertEqual(len(self.channel.sends), 1)
        self.assertEqual(len(self.channel.updates), 2)
        # Every edit targets the same message ref returned by the first send.
        first_ref = self.channel.sends[0][2]
        self.assertTrue(all(u[1] == first_ref for u in self.channel.updates))

    def test_progress_is_throttled_and_updates_same_message(self):
        self.notifier.handle(_event("operation.created"))
        # First progress emits (stage change from None); tiny follow-up suppressed.
        self.notifier.handle(_event("operation.progress", stage="spider", progress=5))
        self.notifier.handle(_event("operation.progress", stage="spider", progress=7))

        self.assertEqual(len(self.channel.sends), 1)          # only the QUEUED message
        self.assertEqual(len(self.channel.updates), 1)        # one throttled progress edit

    def test_terminal_clears_state(self):
        self.notifier.handle(_event("operation.created"))
        self.notifier.handle(_event("operation.completed"))
        # A brand-new lifecycle for the same id starts a fresh message.
        self.notifier.handle(_event("operation.created"))
        self.assertEqual(len(self.channel.sends), 2)

    def test_identical_rerender_is_not_redelivered(self):
        # An event that renders a body identical to the current one carries no
        # new information and must NOT trigger another edit (no spam).
        self.notifier.handle(_event("operation.created"))
        self.notifier.handle(_event("operation.started"))
        edits_after_start = len(self.channel.updates)
        # A second identical 'started' renders the same RUNNING card.
        self.notifier.handle(_event("operation.started"))
        self.assertEqual(len(self.channel.updates), edits_after_start)  # deduped
        # A meaningful change (new phase) still delivers.
        self.notifier.handle(_event("operation.completed"))
        self.assertEqual(len(self.channel.updates), edits_after_start + 1)


class FallbackChannelStrategyTests(unittest.TestCase):
    def setUp(self):
        # All-unsupported: append-only, lifecycle-only.
        self.channel = FakeChannel("email", ChannelCapabilities())
        self.notifier = OperationNotifier(
            NotificationService([self.channel]),
            channel="email",
            destination="ops@example.com",
            lifecycle_events=LIFECYCLE,
            progress_events=PROGRESS,
            clock=FakeClock(),
        )

    def test_new_message_per_lifecycle_transition(self):
        self.notifier.handle(_event("operation.created"))
        self.notifier.handle(_event("operation.started"))
        self.notifier.handle(_event("operation.failed", error="boom"))

        self.assertEqual(len(self.channel.sends), 3)
        self.assertEqual(len(self.channel.updates), 0)

    def test_progress_skipped_when_unsupported(self):
        self.notifier.handle(_event("operation.created"))
        self.notifier.handle(_event("operation.progress", stage="spider", progress=50))

        self.assertEqual(len(self.channel.sends), 1)  # progress produced nothing
        self.assertEqual(len(self.channel.updates), 0)


class BestEffortDeliveryTests(unittest.TestCase):
    def test_delivery_failure_does_not_propagate(self):
        class BrokenChannel(FakeChannel):
            def send(self, destination, message):
                raise RuntimeError("channel down")

        channel = BrokenChannel("chat", ChannelCapabilities())
        notifier = OperationNotifier(
            NotificationService([channel]),
            channel="chat",
            destination="C1",
            lifecycle_events=LIFECYCLE,
            progress_events=PROGRESS,
            logger=_NullLogger(),
        )
        # Must not raise.
        notifier.handle(_event("operation.created"))


class _NullLogger:
    def error(self, *args, **kwargs):
        pass


if __name__ == "__main__":
    unittest.main()
