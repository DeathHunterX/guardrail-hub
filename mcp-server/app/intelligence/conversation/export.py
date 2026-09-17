"""JSONL export and audit hash chain for conversation transcripts.

Authority: Conversation Standard CV-7 (audit is mandatory), CV-8 (original content
preserved in the audit mechanism).

Each exported line is a JSON object representing a message.  The export is signed
with a hash chain so consumers can verify the transcript has not been tampered
with: each line's hash covers the previous line's hash + the current line's
content.

The hash chain uses SHA-256.  The first line's ``prev_hash`` is the empty
string (the genesis hash).  This is the standard blockchain-style hash chain,
not a cryptographic signature — the chain is verifiable without a key.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import IO, TextIO

from app.intelligence.conversation.message import Message
from app.intelligence.conversation.store import ConversationSummary


GENESIS_HASH = ""


def _sha256(data: str) -> str:
    """Return the lowercase hex digest of SHA-256 applied to *data*."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _message_hash(prev_hash: str, msg: Message) -> str:
    """Compute the hash for a single message in the chain.

    The chain covers: previous_hash + role + content + timestamp + redacted flag.
    Metadata is intentionally excluded to avoid non-deterministic ordering issues.
    """
    payload = f"{prev_hash}|{msg.role}|{msg.content}|{msg.timestamp.isoformat()}|{msg.redacted}"
    return _sha256(payload)


class HashChain:
    """Verifiable hash chain over a sequence of messages.

    Each line's hash covers the previous line's hash + the current message.
    Verification recomputes all hashes in order and checks that the stored
    hashes match.
    """

    def __init__(self, *, genesis: str = GENESIS_HASH) -> None:
        self._genesis = genesis
        self._prev_hash: str = genesis
        self._line_hashes: list[str] = []

    @property
    def prev_hash(self) -> str:
        """The hash of the previous line; the starting point for the next."""
        return self._prev_hash

    def extend(self, messages: Sequence[Message]) -> list[str]:
        """Append *messages* to the chain, returning the new hashes."""
        new_hashes: list[str] = []
        for msg in messages:
            h = _message_hash(self._prev_hash, msg)
            new_hashes.append(h)
            self._line_hashes.append(h)
            self._prev_hash = h
        return new_hashes

    def verify(self, messages: Sequence[Message], hashes: Sequence[str]) -> bool:
        """Return True iff the hash chain over *messages* matches *hashes*."""
        if len(messages) != len(hashes):
            return False
        prev = self._genesis
        for msg, expected in zip(messages, hashes):
            h = _message_hash(prev, msg)
            if h != expected:
                return False
            prev = h
        return True

    @property
    def line_hashes(self) -> list[str]:
        """The full list of hashes in insertion order."""
        return list(self._line_hashes)


def export_jsonl(
    summary: ConversationSummary,
    output: TextIO,
    sign: bool = True,
) -> HashChain:
    """Export a conversation to JSONL, optionally signing with a hash chain.

    Each line is a JSON object::

        {
            "index": 0,
            "role": "user",
            "content": "Hello",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "redacted": false,
            "metadata": {"model_id": "gpt-4"},
            "hash": "<hex>"
        }

    The ``hash`` field is the hash chain value for that line (present only when
    ``sign=True``).  ``prev_hash`` of the first line is the empty string.

    Args:
        summary: The conversation snapshot to export.
        output: A file-like object opened in text mode for writing.
        sign: Whether to compute and include hash chain values.

    Returns:
        The HashChain so callers can verify or extend it later.
    """
    chain = HashChain() if sign else None
    messages = summary.messages

    if sign:
        line_hashes = chain.extend(messages)  # type: ignore[union-attr]

    for i, msg in enumerate(messages):
        line_hash = line_hashes[i] if sign else None
        record = {
            "index": i,
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "redacted": msg.redacted,
            "metadata": msg.metadata_dict,
        }
        if line_hash is not None:
            record["hash"] = line_hash
        output.write(json.dumps(record, ensure_ascii=False) + "\n")

    return chain  # type: ignore[return-value]


# Re-export Sequence for use in type stubs above.
from collections.abc import Sequence
