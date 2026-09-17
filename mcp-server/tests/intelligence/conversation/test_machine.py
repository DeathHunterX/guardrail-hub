"""Tests for the conversation state machine."""

import unittest

from app.intelligence.conversation.machine import can_transition_to, requires_audit
from app.intelligence.conversation.state import ConversationState


class TestCanTransitionTo(unittest.TestCase):

    def test_created_to_open_valid(self):
        self.assertTrue(can_transition_to(ConversationState.CREATED, ConversationState.OPEN))

    def test_open_to_closed_valid(self):
        self.assertTrue(can_transition_to(ConversationState.OPEN, ConversationState.CLOSED))

    def test_closed_to_archived_valid(self):
        self.assertTrue(can_transition_to(ConversationState.CLOSED, ConversationState.ARCHIVED))

    def test_archived_to_redacted_purged_valid(self):
        self.assertTrue(
            can_transition_to(
                ConversationState.ARCHIVED, ConversationState.REDACTED_PURGED
            )
        )

    def test_created_to_closed_invalid(self):
        self.assertFalse(
            can_transition_to(ConversationState.CREATED, ConversationState.CLOSED)
        )

    def test_open_to_archived_invalid(self):
        self.assertFalse(
            can_transition_to(ConversationState.OPEN, ConversationState.ARCHIVED)
        )

    def test_closed_to_open_invalid(self):
        # Cannot reopen a closed conversation.
        self.assertFalse(
            can_transition_to(ConversationState.CLOSED, ConversationState.OPEN)
        )

    def test_open_to_created_invalid(self):
        self.assertFalse(
            can_transition_to(ConversationState.OPEN, ConversationState.CREATED)
        )

    def test_closed_to_redacted_invalid(self):
        # REDACTED_PURGED is only reachable from ARCHIVED.
        self.assertFalse(
            can_transition_to(ConversationState.CLOSED, ConversationState.REDACTED_PURGED)
        )

    def test_redacted_purged_is_absorbing(self):
        # Nothing transitions from REDACTED_PURGED.
        for state in ConversationState:
            self.assertFalse(
                can_transition_to(ConversationState.REDACTED_PURGED, state)
            )

    def test_archived_is_absorbing(self):
        # Nothing transitions from ARCHIVED except REDACTED_PURGED.
        for state in ConversationState:
            if state != ConversationState.REDACTED_PURGED:
                self.assertFalse(
                    can_transition_to(ConversationState.ARCHIVED, state)
                )

    def test_closed_is_absorbing(self):
        # Nothing transitions from CLOSED except ARCHIVED.
        for state in ConversationState:
            if state != ConversationState.ARCHIVED:
                self.assertFalse(
                    can_transition_to(ConversationState.CLOSED, state)
                )


class TestRequiresAudit(unittest.TestCase):

    def test_valid_transition_requires_audit(self):
        self.assertTrue(
            requires_audit(ConversationState.CREATED, ConversationState.OPEN)
        )

    def test_invalid_transition_does_not_require_audit(self):
        self.assertFalse(
            requires_audit(ConversationState.CREATED, ConversationState.CLOSED)
        )


if __name__ == "__main__":
    unittest.main()
