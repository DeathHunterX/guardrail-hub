"""Unit tests for the NotificationService routing behaviour."""

import unittest

from app.core.ports.notification_channel import NotificationChannel
from app.services.notification.notification import Notification
from app.services.notification.notification_service import (
    NotificationService,
    UnknownChannelError,
)


class FakeChannel(NotificationChannel):
    """In-memory channel that records deliveries (or fails on demand)."""

    def __init__(self, name: str, fail: bool = False) -> None:
        self._name = name
        self._fail = fail
        self.sent: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return self._name

    def send(self, destination: str, message: str) -> None:
        if self._fail:
            raise RuntimeError("delivery boom")
        self.sent.append((destination, message))


class NotificationServiceTests(unittest.TestCase):
    def test_routes_to_matching_channel(self):
        slack = FakeChannel("slack")
        service = NotificationService([slack])

        service.notify(Notification(channel="slack", destination="C1", message="hi"))

        self.assertEqual(slack.sent, [("C1", "hi")])

    def test_routes_only_to_target_channel(self):
        slack = FakeChannel("slack")
        other = FakeChannel("other")
        service = NotificationService([slack, other])

        service.notify(Notification(channel="other", destination="D1", message="yo"))

        self.assertEqual(other.sent, [("D1", "yo")])
        self.assertEqual(slack.sent, [])

    def test_unknown_channel_raises(self):
        service = NotificationService([FakeChannel("slack")])

        with self.assertRaises(UnknownChannelError):
            service.notify(
                Notification(channel="discord", destination="X", message="m")
            )

    def test_delivery_error_propagates(self):
        service = NotificationService([FakeChannel("slack", fail=True)])

        with self.assertRaises(RuntimeError):
            service.notify(Notification(channel="slack", destination="C1", message="m"))

    def test_channels_property_lists_names(self):
        service = NotificationService([FakeChannel("slack"), FakeChannel("other")])

        self.assertEqual(set(service.channels), {"slack", "other"})


if __name__ == "__main__":
    unittest.main()
