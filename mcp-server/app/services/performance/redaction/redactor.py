"""Artifact redaction — strip secrets before anything is persisted.

Performance artifacts (JTL results, engine logs) can contain the request and
response headers of the target under test. Those must never reach durable
storage or logs (ADR-0010 §5 S4 / INV4 / INV10, and guardrail G1). Redaction
runs on the worker, immediately before persistence and while the raw artifacts
still live in the isolated workspace — so unredacted secrets never cross the
worker boundary.

Exactly the S4 set is redacted, and nothing speculative beyond it:

- sensitive headers (value replaced, name kept): Authorization,
  Proxy-Authorization, Cookie, Set-Cookie, X-API-Key, X-Amz-Security-Token;
- JWTs anywhere (``eyJ…`` three-segment tokens), even outside a header;
- HTTP Basic credentials (``Basic <base64>``).

The core :func:`redact_text` is pure and total; :func:`redact_file` and
:func:`redact_artifacts` apply it to files/artifact sets in place.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from app.services.performance.engine.dto import ArtifactSet

_PLACEHOLDER = "[REDACTED]"

# Header names whose *value* is a secret. Matched case-insensitively, per line,
# with the name preserved so the artifact stays readable ("Cookie: [REDACTED]").
_SENSITIVE_HEADERS = (
    "Authorization",
    "Proxy-Authorization",
    "Cookie",
    "Set-Cookie",
    "X-API-Key",
    "X-Amz-Security-Token",
)

_HEADER_PATTERNS = tuple(
    re.compile(rf"(?im)^(\s*{re.escape(name)}\s*:\s*)[^\r\n]*$")
    for name in _SENSITIVE_HEADERS
)

# A JWT: three base64url segments; the first always starts ``eyJ`` (``{"``).
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

# HTTP Basic credentials, wherever they appear.
_BASIC_PATTERN = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=]+")

# Text-like files worth scanning inside a report directory artifact.
_TEXT_SUFFIXES = frozenset({".jtl", ".xml", ".csv", ".log", ".txt", ".json", ".html", ".htm", ".js"})


def redact_text(text: str) -> str:
    """Return *text* with every S4 secret replaced by a placeholder."""
    for pattern in _HEADER_PATTERNS:
        text = pattern.sub(rf"\1{_PLACEHOLDER}", text)
    text = _JWT_PATTERN.sub("[REDACTED_JWT]", text)
    text = _BASIC_PATTERN.sub(f"Basic {_PLACEHOLDER}", text)
    return text


def redact_file(path: Path) -> None:
    """Redact *path* in place. No-op for a binary/unreadable or unchanged file."""
    try:
        original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return  # not text (or unreadable) — no header secrets to strip
    redacted = redact_text(original)
    if redacted != original:
        path.write_text(redacted, encoding="utf-8")


def redact_artifacts(artifacts: ArtifactSet) -> None:
    """Redact every text artifact in *artifacts*, before persistence (INV4).

    File artifacts are redacted directly; a directory artifact (e.g. the HTML
    report) is walked and its text-like files are redacted.
    """
    for artifact in artifacts.artifacts:
        path = artifact.path
        if path.is_file():
            redact_file(path)
        elif path.is_dir():
            for child in _text_files(path):
                redact_file(child)


def _text_files(directory: Path) -> Iterable[Path]:
    for child in directory.rglob("*"):
        if child.is_file() and child.suffix.lower() in _TEXT_SUFFIXES:
            yield child
