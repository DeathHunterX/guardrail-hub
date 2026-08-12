"""ConversationState — the closed set of states a conversation can occupy.

Authority: Conversation Standard CV-4 (state machine is closed), CV-6
(terminal states are absorbing), CV-5 (transitions are explicit).

The set is closed: new states are added by an ADR, not by code.
Each state exposes whether it is terminal so callers can guard against
illegal transitions without duplicating the logic.
"""

from enum import Enum


class ConversationState(str, Enum):
    """The lifecycle stages of a conversation.

    Valid progression::

        Created -> Open -> Closed -> Archived
                                      |
                         Redacted-purged  (terminal, absorbing)

    A terminal state is absorbing: once reached, a conversation can never
    leave it. The state machine is closed — no new states are added in code.
    """

    CREATED = "created"   # Conversation exists; no messages yet.
    OPEN = "open"        # Active, accepting messages.
    CLOSED = "closed"    # Finished; no new messages accepted.
    ARCHIVED = "archived"  # Retired; kept for audit/replay.
    REDACTED_PURGED = "redacted_purged"  # All PII removed; terminal.

    @property
    def is_terminal(self) -> bool:
        """Whether this state is terminal and absorbing.

        A terminal state is permanent: once a conversation enters it, it can
        never transition to any other state. The conversation is immutable
        from this point forward.
        """
        return self in _TERMINAL_STATES


_TERMINAL_STATES = frozenset(
    {
        ConversationState.CLOSED,
        ConversationState.ARCHIVED,
        ConversationState.REDACTED_PURGED,
    }
)
