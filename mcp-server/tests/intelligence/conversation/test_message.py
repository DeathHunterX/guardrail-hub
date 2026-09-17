"""Tests for Message immutability and validation."""

import unittest
from datetime import datetime, timezone

from app.intelligence.conversation.message import Message


class TestMessage(unittest.TestCase):

    def test_construct_user_message(self):
        msg = Message(role="user", content="Hello")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello")
        self.assertFalse(msg.redacted)
        self.assertIsNotNone(msg.timestamp)
        self.assertEqual(msg.metadata, ())

    def test_construct_assistant_message(self):
        msg = Message(role="assistant", content="Hi there", name="assistant-1")
        self.assertEqual(msg.role, "assistant")
        self.assertEqual(msg.content, "Hi there")
        self.assertEqual(msg.name, "assistant-1")

    def test_construct_system_message(self):
        msg = Message(role="system", content="You are helpful.")
        self.assertEqual(msg.role, "system")

    def test_metadata_dict(self):
        msg = Message(role="user", content="Hi", metadata={"key": "val"})
        self.assertEqual(msg.metadata_dict, {"key": "val"})

    def test_frozen_immutable(self):
        msg = Message(role="user", content="Hello")
        with self.assertRaises(Exception):  # frozen dataclass
            msg.content = "Changed"

    def test_role_validation_rejects_invalid(self):
        with self.assertRaises(ValueError) as ctx:
            Message(role="bot", content="not allowed")
        self.assertIn("bot", str(ctx.exception))

    def test_role_validation_accepts_valid_roles(self):
        for role in ("system", "user", "assistant"):
            msg = Message(role=role, content="ok")
            self.assertEqual(msg.role, role)

    def test_slots_available(self):
        msg = Message(role="user", content="test")
        self.assertTrue(hasattr(msg, "__slots__"))

    def test_redacted_flag(self):
        msg = Message(role="user", content="[REDACTED]", redacted=True)
        self.assertTrue(msg.redacted)
        self.assertEqual(msg.content, "[REDACTED]")

    def test_timestamp_default_is_utc(self):
        msg = Message(role="user", content="hello")
        self.assertEqual(msg.timestamp.tzinfo, timezone.utc)

    def test_timestamp_explicit(self):
        ts = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        msg = Message(role="user", content="hello", timestamp=ts)
        self.assertEqual(msg.timestamp, ts)


if __name__ == "__main__":
    unittest.main()
