"""Concrete adapters for the credential setup ports.

These bind the :mod:`app.intelligence.setup.ports` Protocols to real I/O:

  - :class:`MaskedSecretPrompt` reads a secret with masked terminal feedback.
  - :class:`StreamOutputWriter` writes user-facing lines to a text stream.
  - :class:`Boto3AwsCredentialDetector` performs a presence-only check of the
    AWS SDK credential chain.

Terminal-specific masked input remains contained in this adapter layer; setup
decision logic stays in the service and CLI flows.
"""

from __future__ import annotations

import codecs
import os
import sys
from typing import Callable, Optional, TextIO

from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.setup.ports import (
    AwsCredentialDetector,
    OutputWriter,
    SecretPrompt,
)


class SecureInputUnavailableError(EOFError):
    """Masked credential entry is unavailable without an interactive terminal."""


class MaskedSecretPrompt(SecretPrompt):
    """Read a credential with masks, never echoing its entered characters.

    Windows uses the console's ``msvcrt`` character primitives. POSIX terminals
    use cbreak mode and always restore the previous terminal attributes. A
    redirected or otherwise non-interactive stream fails closed rather than
    falling back to visible plaintext input.
    """

    def read_secret(self, prompt_text: str) -> str:
        """Return the exact entered credential while rendering masks only."""
        _require_interactive_terminal(sys.stdin, sys.stdout)
        if sys.platform == "win32":
            return _read_windows_masked_secret(prompt_text)
        return _read_posix_masked_secret(prompt_text)


def _require_interactive_terminal(input_stream: TextIO, output: TextIO) -> None:
    if not input_stream.isatty() or not output.isatty():
        raise SecureInputUnavailableError(
            "secure credential entry requires an interactive terminal"
        )


def _read_windows_masked_secret(
    prompt_text: str,
    *,
    getwch: Callable[[], str] | None = None,
    putwch: Callable[[str], None] | None = None,
) -> str:
    """Collect Windows console input with one ``*`` per accepted character."""
    if getwch is None or putwch is None:
        try:
            import msvcrt
        except ImportError as exc:  # pragma: no cover - Windows-only module.
            raise SecureInputUnavailableError(
                "secure credential entry requires an interactive Windows console"
            ) from exc
        getwch = getwch or msvcrt.getwch
        putwch = putwch or msvcrt.putwch

    def write(text: str) -> None:
        for character in text:
            putwch(character)

    def read_character() -> str | None:
        character = getwch()
        if character in ("\x00", "\xe0"):
            getwch()
            return None
        return character

    return _collect_masked_secret(prompt_text, read_character, write)


def _read_posix_masked_secret(
    prompt_text: str,
    *,
    input_stream: TextIO | None = None,
    output: TextIO | None = None,
    terminal_api=None,
    set_cbreak: Callable[[int], None] | None = None,
    read_byte: Callable[[int, int], bytes] = os.read,
) -> str:
    """Collect masked input in POSIX cbreak mode and always restore state."""
    input_stream = input_stream or sys.stdin
    output = output or sys.stdout
    _require_interactive_terminal(input_stream, output)
    if terminal_api is None:
        import termios as terminal_api
    if set_cbreak is None:
        from tty import setcbreak as set_cbreak

    descriptor = input_stream.fileno()
    previous_mode = terminal_api.tcgetattr(descriptor)
    encoding = getattr(input_stream, "encoding", None) or "utf-8"
    decoder = codecs.getincrementaldecoder(encoding)(errors="surrogateescape")
    pending_characters: list[str] = []

    def write(text: str) -> None:
        output.write(text)
        output.flush()

    def read_character() -> str | None:
        while True:
            if pending_characters:
                return pending_characters.pop(0)
            raw = read_byte(descriptor, 1)
            if raw == b"":
                trailing = decoder.decode(b"", final=True)
                if trailing:
                    pending_characters.extend(trailing)
                    continue
                raise EOFError
            decoded = decoder.decode(raw)
            if decoded:
                pending_characters.extend(decoded)

    try:
        set_cbreak(descriptor)
        return _collect_masked_secret(prompt_text, read_character, write)
    except KeyboardInterrupt:
        write("\r\n")
        raise
    finally:
        terminal_api.tcsetattr(descriptor, terminal_api.TCSADRAIN, previous_mode)


def _collect_masked_secret(
    prompt_text: str,
    read_character: Callable[[], str | None],
    write: Callable[[str], None],
) -> str:
    """Render masks while retaining only the exact accepted input in memory."""
    value: list[str] = []
    escape_state: str | None = None
    write(prompt_text)
    while True:
        character = read_character()
        if character is None:
            continue
        if escape_state == "prefix":
            if character in ("[", "O"):
                escape_state = "sequence"
                continue
            escape_state = None
        elif escape_state == "sequence":
            if "@" <= character <= "~":
                escape_state = None
            continue
        if character == "\x1b":
            escape_state = "prefix"
            continue
        if character in ("\r", "\n"):
            write("\r\n")
            return "".join(value)
        if character == "\x03":
            write("\r\n")
            raise KeyboardInterrupt
        if character in ("\x04", "\x1a"):
            write("\r\n")
            raise EOFError
        if character in ("\b", "\x7f"):
            if value:
                value.pop()
                write("\b \b")
            continue
        if ord(character) < 32:
            continue
        value.append(character)
        write("*")


class StreamOutputWriter(OutputWriter):
    """Writes user-facing output lines to a text stream (stdout by default).

    This is presentation output only; secrets are never routed here.
    """

    def __init__(self, stream: Optional[TextIO] = None) -> None:
        """Store the target stream, defaulting to the live ``sys.stdout``.

        The default is resolved lazily (at write time) so that redirection of
        ``sys.stdout`` after construction is still honoured.
        """
        self._stream = stream

    def write_line(self, text: str) -> None:
        """Write a single line followed by a newline, then flush."""
        self.write(text + "\n")
        self.flush()

    def write(self, text: str) -> None:
        """Write terminal presentation without imposing line structure."""
        stream = self._stream if self._stream is not None else sys.stdout
        stream.write(text)

    def flush(self) -> None:
        """Force terminal presentation through any stdout buffering layer."""
        stream = self._stream if self._stream is not None else sys.stdout
        stream.flush()

    @property
    def encoding(self) -> str | None:
        """Expose the destination encoding so progress UI can choose safe glyphs."""
        stream = self._stream if self._stream is not None else sys.stdout
        return stream.encoding


class Boto3AwsCredentialDetector(AwsCredentialDetector):
    """Presence-only check of the AWS SDK credential chain via boto3.

    boto3 is an optional dependency. If it is not installed, or the credential
    chain cannot be evaluated, this raises :class:`LLMConfigurationError` so the
    CLI can report a clear Bedrock credential/setup error. It never reads,
    returns, or logs the actual AWS credential values.
    """

    def is_available(self) -> bool:
        """Return True if the AWS credential chain resolves to usable credentials.

        Raises:
            LLMConfigurationError: If boto3 is not installed or the credential
                chain cannot be evaluated. The message contains no secret data.
        """
        try:
            import boto3  # Imported lazily; optional dependency.
        except ImportError as exc:
            raise LLMConfigurationError(
                "AWS support requires the 'boto3' package, which is not "
                "installed; install it to configure AWS (Bedrock) providers."
            ) from exc

        try:
            session = boto3.Session()
            credentials = session.get_credentials()
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error.
            # Do not surface the underlying SDK error verbatim: it may embed
            # profile names, ARNs, or partial identifiers. Report a clean,
            # secret-free configuration error instead.
            raise LLMConfigurationError(
                "Unable to evaluate the AWS credential chain."
            ) from exc

        # get_credentials() returns None when no credentials could be resolved.
        return credentials is not None


__all__ = [
    "Boto3AwsCredentialDetector",
    "MaskedSecretPrompt",
    "SecureInputUnavailableError",
    "StreamOutputWriter",
]
