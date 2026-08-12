"""Tests for InMemoryConversationStore."""

import unittest
from datetime import datetime, timezone

from app.intelligence.conversation.infrastructure.in_memory_store import (
    InMemoryConversationStore,
)
from app.intelligence.conversation.message import Message
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import (
    ConversationClosedError,
    ConversationNotFoundError,
)


class TestInMemoryConversationStore(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryConversationStore()

    # --- create ---

    def test_create_default_state(self):
        s = self.store.create("c1")
        self.assertEqual(s.conversation_id, "c1")
        self.assertEqual(s.state, ConversationState.CREATED)
        self.assertEqual(s.messages, ())
        self.assertIsNotNone(s.created_at)

    def test_create_explicit_initial_state(self):
        s = self.store.create("c1", initial_state=ConversationState.OPEN)
        self.assertEqual(s.state, ConversationState.OPEN)

    def test_create_duplicate_raises(self):
        self.store.create("c1")
        with self.assertRaises(KeyError):
            self.store.create("c1")

    # --- read ---

    def test_read_not_found_returns_none(self):
        self.assertIsNone(self.store.read("nonexistent"))

    def test_read_returns_summary(self):
        self.store.create("c1")
        s = self.store.read("c1")
        self.assertEqual(s.conversation_id, "c1")
        self.assertEqual(s.state, ConversationState.CREATED)

    # --- append ---

    def test_append_user_message(self):
        self.store.create("c1")
        msg = Message(role="user", content="Hello")
        s = self.store.append("c1", msg)
        self.assertEqual(len(s.messages), 1)
        self.assertEqual(s.messages[0].content, "Hello")

    def test_append_preserves_immutability(self):
        self.store.create("c1")
        msg = Message(role="user", content="Hello")
        s1 = self.store.append("c1", msg)
        msg2 = Message(role="assistant", content="Hi")
        s2 = self.store.append("c1", msg2)
        # Each summary returns a fresh tuple.
        self.assertEqual(len(s1.messages), 1)
        self.assertEqual(len(s2.messages), 2)

    def test_append_not_found_raises(self):
        with self.assertRaises(ConversationNotFoundError):
            self.store.append("nonexistent", Message(role="user", content="oops"))

    def test_append_terminal_rejected(self):
        self.store.create("c1", initial_state=ConversationState.OPEN)
        self.store.transition_to("c1", ConversationState.CLOSED)
        with self.assertRaises(ConversationClosedError):
            self.store.append("c1", Message(role="user", content="oops"))

    # --- transition_to ---

    def test_transition_created_to_open(self):
        self.store.create("c1")
        s = self.store.transition_to("c1", ConversationState.OPEN)
        self.assertEqual(s.state, ConversationState.OPEN)

    def test_transition_open_to_closed(self):
        self.store.create("c1", initial_state=ConversationState.OPEN)
        s = self.store.transition_to("c1", ConversationState.CLOSED)
        self.assertEqual(s.state, ConversationState.CLOSED)

    def test_transition_invalid_rejected(self):
        self.store.create("c1")
        # CREATED -> CLOSED is not in the transition graph; store raises ValueError.
        with self.assertRaises(ValueError):
            self.store.transition_to("c1", ConversationState.CLOSED)

    def test_transition_from_terminal_rejected(self):
        self.store.create("c1", initial_state=ConversationState.OPEN)
        self.store.transition_to("c1", ConversationState.CLOSED)
        with self.assertRaises(ConversationClosedError):
            self.store.transition_to("c1", ConversationState.ARCHIVED)

    def test_transition_not_found_raises(self):
        with self.assertRaises(ConversationNotFoundError):
            self.store.transition_to("nonexistent", ConversationState.OPEN)

    # --- list_states ---

    def test_list_states_returns_history(self):
        self.store.create("c1")
        self.store.transition_to("c1", ConversationState.OPEN)
        self.store.transition_to("c1", ConversationState.CLOSED)
        history = self.store.list_states("c1")
        self.assertEqual(len(history), 3)  # CREATED, OPEN, CLOSED
        self.assertEqual(history[0][0], ConversationState.CREATED)
        self.assertEqual(history[1][0], ConversationState.OPEN)
        self.assertEqual(history[2][0], ConversationState.CLOSED)

    def test_list_states_not_found_raises(self):
        with self.assertRaises(ConversationNotFoundError):
            self.store.list_states("nonexistent")


if __name__ == "__main__":
    unittest.main()
