"""Tests for conversation typed events."""

import unittest

from app.intelligence.conversation.events import (
    ConversationCreated,
    MessageAppended,
    RedactionPerformed,
    StateTransitioned,
)
from app.intelligence.conversation.state import ConversationState


class TestConversationEvents(unittest.TestCase):

    def test_conversation_created_name(self):
        ev = ConversationCreated(conversation_id="c1", initial_state=ConversationState.CREATED)
        self.assertEqual(ev.name, "conversation.created")
        self.assertEqual(ev.conversation_id, "c1")
        self.assertEqual(ev.initial_state, ConversationState.CREATED)
        self.assertIsNotNone(ev.occurred_at)

    def test_state_transitioned_name(self):
        ev = StateTransitioned(
            conversation_id="c1",
            from_state=ConversationState.CREATED,
            to_state=ConversationState.OPEN,
        )
        self.assertEqual(ev.name, "conversation.state_transitioned")
        self.assertEqual(ev.from_state, ConversationState.CREATED)
        self.assertEqual(ev.to_state, ConversationState.OPEN)

    def test_message_appended_name(self):
        ev = MessageAppended(
            conversation_id="c1",
            message_index=0,
            role="user",
            redacted=False,
        )
        self.assertEqual(ev.name, "conversation.message_appended")
        self.assertEqual(ev.message_index, 0)
        self.assertEqual(ev.role, "user")

    def test_redaction_performed_name(self):
        ev = RedactionPerformed(
            conversation_id="c1",
            message_index=0,
            redaction_policy="default",
        )
        self.assertEqual(ev.name, "conversation.redaction_performed")
        self.assertEqual(ev.redaction_policy, "default")

    def test_events_are_frozen(self):
        ev = ConversationCreated(conversation_id="c1")
        with self.assertRaises(Exception):  # frozen dataclass
            ev.conversation_id = "c2"

    def test_events_have_version(self):
        self.assertEqual(ConversationCreated.__dataclass_fields__["conversation_id"].name, "conversation_id")


if __name__ == "__main__":
    unittest.main()
