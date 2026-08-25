"""Concrete adapters for the credential setup ports.

These bind the :mod:`app.intelligence.setup.ports` Protocols to real I/O:

  - :class:`GetpassSecretPrompt` reads a secret without echoing it (getpass).
  - :class:`StreamOutputWriter` writes user-facing lines to a text stream.
  - :class:`Boto3AwsCredentialDetector` performs a presence-only check of the
    AWS SDK credential chain.

They are intentionally thin — all decision logic lives in
:class:`app.intelligence.setup.service.CredentialSetupService`, so these
adapters need no unit tests of their own and the service can be tested with
in-memory fakes instead.
"""

from __future__ import annotations

import getpass as _getpass_module
import sys
from typing import Callable, Optional, TextIO

from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.setup.ports import (
    AwsCredentialDetector,
    OutputWriter,
    SecretPrompt,
)


class GetpassSecretPrompt(SecretPrompt):
    """Reads a secret from the terminal without echoing the typed characters.

    Wraps :func:`getpass.getpass`. The returned value is handed straight to the
    CredentialStore by the service; this adapter never logs or retains it.
    """

    def __init__(
        self, getpass_fn: Callable[[str], str] = _getpass_module.getpass
    ) -> None:
        """Store the getpass callable (overridable for testing)."""
        self._getpass_fn = getpass_fn

    def read_secret(self, prompt_text: str) -> str:
        """Return the secret entered by the operator using hidden input."""
        return self._getpass_fn(prompt_text)


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
        stream = self._stream if self._stream is not None else sys.stdout
        stream.write(text + "\n")
        stream.flush()


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
    "GetpassSecretPrompt",
    "StreamOutputWriter",
]
