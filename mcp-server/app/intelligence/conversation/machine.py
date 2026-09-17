"""ConversationMachine — enforces the conversation state transition rules.

Authority: Conversation Standard CV-4 (closed set), CV-5 (explicit transitions),
CV-6 (terminal states are absorbing).

The machine is a pure predicate: it accepts a current state and a target
state, and returns whether the transition is permitted.  It does not execute
transitions, persist changes, or emit events — those responsibilities belong
to the ConversationStore and the audit layer respectively.
"""

from app.intelligence.conversation.state import ConversationState


# Valid transitions: from_state -> set of allowed to_states.
# Order matters for the transition graph (Created -> Open -> ...).
_TRANSITION_GRAPH: dict[ConversationState, frozenset[ConversationState]] = {
    ConversationState.CREATED: frozenset({ConversationState.OPEN}),
    ConversationState.OPEN: frozenset({ConversationState.CLOSED}),
    ConversationState.CLOSED: frozenset({ConversationState.ARCHIVED}),
    ConversationState.ARCHIVED: frozenset({ConversationState.REDACTED_PURGED}),
    ConversationState.REDACTED_PURGED: frozenset(),  # absorbing
}


def can_transition_to(current: ConversationState, target: ConversationState) -> bool:
    """Return whether a transition from current to target is permitted.

    Args:
        current: The conversation's current state.
        target: The desired next state.

    Returns:
        True if the transition is in the allowed graph; False otherwise.

    Note:
        This returns False for all terminal-state targets regardless of
        input — terminal states are absorbing.
    """
    return target in _TRANSITION_GRAPH.get(current, frozenset())


def requires_audit(current: ConversationState, target: ConversationState) -> bool:
    """Return whether a transition requires an audit event.

    Every explicit transition produces an audit entry per CV-5.
    """
    return can_transition_to(current, target)
