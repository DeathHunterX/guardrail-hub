"""Redaction — redaction policy registry and the default redact function.

Authority: Conversation Standard CV-8 (redaction preserves the original).

A redaction policy is a callable ``(content: str) -> str`` that replaces
sensitive content with a placeholder.  Policies are registered by name; the
audit log records which policy was applied so the redaction is auditable
without repeating the policy.

Redaction is always performed on a Message record; it does not mutate the
original.  The conversation store's append path handles the redaction event
emission (via the ConversationStore -> ConversationService -> EventPublisher
chain).  This module provides only the policy registry and the default policy.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

# Default replacement marker — matches the default export placeholder.
DEFAULT_REPLACEMENT = "[REDACTED]"


# Default policy: replaces sequences of non-whitespace characters that look
# like emails, API keys, or national IDs with [REDACTED].
# Conservative — only fires on high-confidence patterns.
_DEFAULT_PATTERNS = [
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),   # email
    re.compile(r"(?i)api[_-]?key['\"]?\s*[:=]\s*['\"]?[\w-]{8,}"),   # api_key = ...
    re.compile(r"(?i)bearer\s+[\w-]{16,}"),                           # Bearer <token>
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),                           # OpenAI sk-
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                            # SSN-like
]


def _default_redactor(content: str) -> str:
    """Default redaction: conservative pattern-based redaction."""
    result = content
    for pattern in _DEFAULT_PATTERNS:
        result = pattern.sub(DEFAULT_REPLACEMENT, result)
    return result


# Policy registry: name -> (redactor callable, replacement marker).
_policy_registry: dict[str, tuple[Callable[[str], str], str]] = {
    "default": (_default_redactor, DEFAULT_REPLACEMENT),
}


def register_policy(
    name: str,
    redactor: Callable[[str], str],
    replacement: str = DEFAULT_REPLACEMENT,
) -> None:
    """Register a named redaction policy.

    Args:
        name: Unique policy identifier used in audit events.
        redactor: A callable that accepts raw content and returns redacted text.
        replacement: The replacement string the policy uses (for audit).
    """
    _policy_registry[name] = (redactor, replacement)


def apply_redaction(
    content: str,
    policy: str = "default",
) -> str:
    """Apply a named redaction policy to content.

    Args:
        content: The raw content to redact.
        policy: The registered policy name.  Defaults to "default".

    Returns:
        The redacted content.

    Raises:
        ValueError: If the policy name is not registered.
    """
    entry = _policy_registry.get(policy)
    if entry is None:
        raise ValueError(f"Redaction policy {policy!r} is not registered")
    redactor, _ = entry
    return redactor(content)


def get_replacement(policy: str = "default") -> str:
    """Return the replacement string used by a registered policy."""
    entry = _policy_registry.get(policy)
    if entry is None:
        raise ValueError(f"Redaction policy {policy!r} is not registered")
    return entry[1]
