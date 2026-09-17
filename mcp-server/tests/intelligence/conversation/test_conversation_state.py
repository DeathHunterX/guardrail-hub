"""Tests for ConversationState."""

import unittest

from app.intelligence.conversation.state import ConversationState


class TestConversationState(unittest.TestCase):

    def test_created_is_not_terminal(self):
        self.assertFalse(ConversationState.CREATED.is_terminal)

    def test_open_is_not_terminal(self):
        self.assertFalse(ConversationState.OPEN.is_terminal)

    def test_closed_is_terminal(self):
        self.assertTrue(ConversationState.CLOSED.is_terminal)

    def test_archived_is_terminal(self):
        self.assertTrue(ConversationState.ARCHIVED.is_terminal)

    def test_redacted_purged_is_terminal(self):
        self.assertTrue(ConversationState.REDACTED_PURGED.is_terminal)

    def test_string_values(self):
        self.assertEqual(ConversationState.CREATED.value, "created")
        self.assertEqual(ConversationState.OPEN.value, "open")
        self.assertEqual(ConversationState.CLOSED.value, "closed")
        self.assertEqual(ConversationState.ARCHIVED.value, "archived")
        self.assertEqual(ConversationState.REDACTED_PURGED.value, "redacted_purged")


if __name__ == "__main__":
    unittest.main()
