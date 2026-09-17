"""Container / orchestrated file-mounted credential backend.

Implements the read-only ``ContainerFileCredentialBackend`` ratified in
ADR-0017 (Container & Orchestrated Credential Delivery). It resolves a
credential from a filesystem-mounted secret directory using one
deployment-agnostic contract:

    provider_id  ->  <secrets_dir>/<provider_id>  ->  secret value

The default ``secrets_dir`` is ``/run/secrets`` -- the conventional mount
point for Docker secrets, Podman secrets, and Kubernetes / orchestrated
projected secret volumes. A single backend serves all three; the only
deployment-specific parameter is the secrets directory (ADR-0017 Decision B).
No orchestrator SDK is used (ADR-0017 Decision C).

Security invariants enforced at this backend boundary (ADR-0017 §5), because
no upstream layer validates ``provider_id`` today:

* INV-1  ``provider_id`` is untrusted input, validated as a single path-safe
         filename component: no separator, no absolute path, no NUL, no
         ``..`` path segment (an identifier that merely contains two adjacent
         dots, such as ``a..b``, is an ordinary filename and is allowed), and
         nothing the filesystem layer cannot encode (e.g. a lone surrogate).
         The resolved target must then remain inside ``secrets_dir`` (verified
         with real-path semantics, not a string prefix comparison). An unsafe id
         is rejected, never sanitized into a different filename, and is always
         rejected as ``CredentialBackendError`` -- no foreign exception type
         escapes this seam.
* INV-3  read-only: ``get`` is supported; ``set`` / ``delete`` raise
         ``CredentialBackendError``.
* INV-5  bounded, regular-file reads: the target must exist, be a regular
         file, be readable by the current process, and be within a bounded
         maximum size. File ownership / mode are advisory, not hard-required
         (rootless Podman and projected volumes legitimately vary).
* INV-6  the secret value never appears in ``repr`` / ``str``, exceptions, or
         logs. This backend performs no logging of file contents. No error
         raised after the file has been read carries a reachable exception
         context, or a reachable frame local, holding the raw bytes: the read
         buffer is scrubbed on every exit path, not only on the branch that
         happened to raise.
"""

from __future__ import annotations

import os
import stat
from typing import ClassVar, Final

from app.intelligence.credentials.base import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
)

# Maximum size (in bytes) of a credential file this backend will read.
#
# API keys, bearer tokens, and even large JWTs are at most a few kilobytes.
# The cap bounds how much is read into memory and fails closed on an
# obviously-wrong mount (an accidentally mounted large file, or an
# attacker-substituted oversized payload) rather than loading it. It is set
# deliberately generous so it never rejects a legitimate credential.
MAX_CREDENTIAL_FILE_SIZE_BYTES: Final[int] = 64 * 1024  # 64 KiB

# Default mount point for file-mounted secrets across Docker, Podman, and
# orchestrated / projected secret volumes (ADR-0017 Decision A/B).
DEFAULT_SECRETS_DIR: Final[str] = "/run/secrets"


class ContainerFileCredentialBackend(CredentialBackend):
    """Read-only credential backend reading secrets from a mounted directory.

    Each credential is a single regular file at ``<secrets_dir>/<provider_id>``
    whose content (minus a single trailing newline) is the credential value.
    This backend never writes: secret files are provisioned by the deployment
    platform / operator, not by the application (ADR-0017 Decision H, INV-3).

    Known residual (INV-6, ``set`` only -- not closed by this module)

        ``set`` refuses with ``CredentialBackendError`` and never inspects the
        plaintext, but the refusal's traceback spans every frame the call passed
        through, and a frame's locals stay reachable via ``exc.__traceback__``
        after the frame exits. :meth:`set` scrubs its own ``credential`` local;
        ``CredentialStore.set`` (``base.py``) and the original caller each still
        hold the same string in frames this module cannot reach. Closing the
        chain requires a ``try/finally: del credential`` around the delegation in
        ``CredentialStore.set`` -- outside this phase's authorized scope -- and
        the *originating* caller's frame is outside the credential layer
        entirely. The mitigating facts: the value is caller-supplied plaintext
        the caller already holds, and no correct deployment calls ``set`` on a
        read-only backend, so this path is a misconfiguration signal rather than
        a normal flow. Recorded here so the gap is not mistaken for closed.

    Args:
        secrets_dir: Directory the mounted secret files live under. Defaults to
            ``/run/secrets``. Not required to exist at construction time.
        max_file_size_bytes: Upper bound on credential-file size. Defaults to
            :data:`MAX_CREDENTIAL_FILE_SIZE_BYTES`. Exposed for testability and
            unusual deployments; it is not wired to any environment variable in
            this phase.
    """

    # Shared message for the two write operations this read-only backend
    # refuses. It names the operation intent, never a secret value.
    _READ_ONLY_MESSAGE: ClassVar[str] = (
        "credentials are provisioned by the deployment platform; "
        "this backend is read-only"
    )

    def __init__(
        self,
        secrets_dir: str = DEFAULT_SECRETS_DIR,
        *,
        max_file_size_bytes: int = MAX_CREDENTIAL_FILE_SIZE_BYTES,
    ) -> None:
        self._secrets_dir = secrets_dir
        self._max_file_size_bytes = max_file_size_bytes

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get(self, provider_id: str) -> str:
        # INV-1: validate the untrusted provider_id and resolve a contained
        # target path before touching the filesystem for a read.
        secret_path = self._resolve_secret_path(provider_id)

        # INV-5: the target must exist, be a regular file, be readable, and be
        # within the size bound. Anything else fails closed.
        try:
            file_stat = os.stat(secret_path)  # path is already fully resolved
        except FileNotFoundError:
            # No file mounted for this provider means no credential.
            raise CredentialNotFoundError(provider_id)
        except OSError as exc:
            raise CredentialBackendError(
                provider_id,
                f"cannot access secret file: {self._os_error_reason(exc)}",
            )

        if not stat.S_ISREG(file_stat.st_mode):
            raise CredentialBackendError(
                provider_id,
                "secret path is not a regular file",
            )

        if file_stat.st_size > self._max_file_size_bytes:
            raise CredentialBackendError(
                provider_id,
                f"secret file exceeds the maximum allowed size "
                f"({self._max_file_size_bytes} bytes)",
            )

        # INV-6 -- secret lifetime. A frame's locals stay reachable through
        # `exc.__traceback__` long after that frame has exited, so any local
        # still bound to the credential when an exception leaves this function
        # is recoverable by an error reporter, debugger, or structured log
        # serializer that walks frames (several do so by default).
        #
        # The scrub is therefore scoped as a *region*, not attached to
        # individual raises: the guarded block below opens BEFORE the first
        # statement that can bind any secret-bearing local and closes at
        # function exit, and its `finally` clears both of them. `finally` runs
        # during exception propagation, before the exception leaves this frame,
        # so the exits that matter are covered -- normal return, any raise
        # present today, any raise added inside the region later, and an
        # asynchronous interruption (a signal handler raising KeyboardInterrupt)
        # landing on essentially any bytecode boundary within the region.
        #
        # Two precise limits, so this is not read as more than it is. An
        # interruption landing on the `del` itself, or between its two names,
        # leaves one local bound; that window is a couple of bytecodes wide and
        # cannot be closed from inside the language. And `handle` is a local of
        # this region too, deliberately not deleted: a closed `BufferedReader`
        # was verified to retain no plaintext, so deleting it would only add
        # noise. What the `finally` guarantees is that the locals which *hold
        # secret material* are gone.
        #
        # An earlier revision scrubbed only `raw` and opened the region after
        # the read had already completed. That left two holes: the read's own
        # `except` handlers ran with the buffer live (a failure from the `with`
        # block's `__exit__` -- a real `close()` error, which POSIX permits and
        # which occurs on network/FUSE/projected mounts -- escaped through
        # them), and the decoded plaintext was never scrubbed at all. Both
        # locals are pre-bound to None so the `finally` can delete them
        # unconditionally, whether or not the read ever reached them.
        raw: bytes | None = None
        decoded: str | None = None
        try:
            try:
                with open(secret_path, "rb") as handle:
                    # Read one extra byte so a file that grew between stat and
                    # read (TOCTOU) is still caught by the size check below.
                    raw = handle.read(self._max_file_size_bytes + 1)
            except PermissionError:
                raise CredentialBackendError(
                    provider_id,
                    "secret file is not readable by the current process",
                )
            except OSError as exc:
                raise CredentialBackendError(
                    provider_id,
                    f"cannot read secret file: {self._os_error_reason(exc)}",
                )

            if len(raw) > self._max_file_size_bytes:
                raise CredentialBackendError(
                    provider_id,
                    f"secret file exceeds the maximum allowed size "
                    f"({self._max_file_size_bytes} bytes)",
                )

            # Fail closed on non-UTF-8 content; never expose the raw bytes.
            #
            # A UnicodeDecodeError carries the offending input in its `object`
            # attribute -- i.e. the raw credential bytes -- so it must not
            # remain reachable from the error that crosses this seam.
            # `raise ... from None` is NOT sufficient: it clears `__cause__`
            # and suppresses *rendering*, but leaves `__context__` bound, so
            # any consumer that walks the exception chain (error reporters,
            # debuggers, structured log serializers) can still recover the
            # credential.
            #
            # Raising *after* the `except` block has exited means no exception
            # is being handled at that point, so no context is attached at
            # all. The strict UTF-8 policy itself is unchanged: there is no
            # fallback encoding and no lossy decode.
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError:
                decoded = None

            if decoded is None:
                raise CredentialBackendError(
                    provider_id,
                    "secret file is not valid UTF-8",
                )

            return self._strip_single_trailing_newline(decoded)
        finally:
            # Deleting the names (rather than rebinding them) leaves nothing
            # for a frame-locals walk to report at all. The returned value is
            # unaffected: it is already held on the interpreter's value stack
            # by the time `finally` runs.
            del raw, decoded

    # ------------------------------------------------------------------
    # Read-only contract (INV-3)
    # ------------------------------------------------------------------

    def set(self, provider_id: str, credential: str) -> None:
        # The `credential` argument is never inspected, logged, or written.
        #
        # INV-6: it is nonetheless a local of THIS frame, so the refusal below
        # would leave the plaintext reachable through `exc.__traceback__`. The
        # scrub closes this frame only. It does NOT make the operation
        # INV-6-clean end to end: `CredentialStore.set` and the original caller
        # both still hold the same string in their own frames, on the same
        # traceback, and neither is reachable from this module. See the class
        # docstring -- that residual is recorded, not solved here.
        try:
            raise CredentialBackendError(provider_id, self._READ_ONLY_MESSAGE)
        finally:
            del credential

    def delete(self, provider_id: str) -> None:
        # No credential parameter, so there is nothing to scrub here.
        raise CredentialBackendError(provider_id, self._READ_ONLY_MESSAGE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_secret_path(self, provider_id: str) -> str:
        """Validate ``provider_id`` (INV-1) and return the contained target path.

        Resolution runs in three stages. :meth:`_validate_provider_id` is pure
        string analysis and touches no filesystem API, so a malformed identifier
        is refused through the credential exception hierarchy before any syscall
        can raise an exception type foreign to this seam.
        :meth:`_validate_secrets_dir` does the same for the configured directory.
        The actual path resolution is then performed inside a guard, because the
        two static checks cannot cover it: resolution also depends on process
        state, so it can fail even when every input was valid.

        Raises:
            CredentialBackendError: the provider_id is unsafe, the configured
                directory is unusable, the path cannot be resolved, or the
                resolved target escapes ``secrets_dir``. The message may name the
                provider_id but never any file content.
        """
        self._validate_provider_id(provider_id)
        secrets_dir = self._validate_secrets_dir(provider_id)

        # Resolve with real-path semantics (following symlinks, e.g. Kubernetes
        # projected volumes) and confirm the resolved target is contained within
        # the resolved secrets directory. This is a correct component-wise
        # containment check, not a string prefix comparison.
        #
        # The whole resolution is guarded, not merely its inputs. Validating the
        # inputs closes only the statically-detectable failures; resolution reads
        # process state as well, so a valid relative ``secrets_dir`` still makes
        # `os.path.realpath` call `os.getcwd()`, which raises OSError when the
        # working directory has been removed or has lost its execute bit. That
        # would cross this seam as a bare OSError and bypass the
        # CredentialStoreError mapping the routing layer relies on -- the exact
        # failure the input validation exists to prevent, reached by a different
        # route. Guarding the region covers it and any other OSError/ValueError a
        # path API may raise here, including ones added later.
        #
        # The reason is captured and re-raised after the handler exits, matching
        # the pattern used by the validators above: nothing is chained, so no
        # context object carrying the configured path stays reachable.
        resolved_target = ""
        contained = False
        resolve_error: str | None = None
        try:
            resolved_dir = os.path.realpath(secrets_dir)
            candidate = os.path.join(resolved_dir, provider_id)
            resolved_target = os.path.realpath(candidate)
            contained = self._is_contained(resolved_dir, resolved_target)
        except (OSError, ValueError) as exc:
            # `strerror` exists on OSError only; ValueError falls back to its
            # type name. Neither renders the configured path.
            resolve_error = getattr(exc, "strerror", None) or type(exc).__name__

        if resolve_error is not None:
            raise CredentialBackendError(
                provider_id,
                f"cannot resolve the secret path: {resolve_error}",
            )

        if not contained:
            raise CredentialBackendError(
                provider_id,
                "resolved secret path escapes the configured secrets directory",
            )

        return resolved_target

    def _validate_secrets_dir(self, provider_id: str) -> str:
        """Return ``secrets_dir``, refusing a value no path API can accept.

        ``secrets_dir`` is deployment-supplied (a compose file, a Helm value, an
        operator's flag) and is not validated at construction time, because the
        directory legitimately may not exist yet. It therefore reaches
        ``os.path.realpath`` unchecked on the first ``get``. A non-string, an
        embedded NUL, or a value this filesystem cannot encode makes that call
        raise ``TypeError``/``ValueError`` -- exception types foreign to the
        credential seam, which bypass the ``CredentialStoreError`` mapping the
        routing layer relies on. Misconfiguration must fail closed *as a
        credential error*, not as an unhandled crash.

        This is a configuration check, so it does not reuse the provider_id
        rules: a directory path legitimately contains separators, may be
        absolute, and may contain ``..``. Only ``str`` is accepted, so the seam
        has one canonical type: ``bytes`` and ``os.PathLike`` would resolve
        natively but are refused rather than silently normalised, because a
        ``bytes`` directory joined with a ``str`` provider_id fails later and
        further from its cause. Whether the directory exists is left to the read
        path (INV-5), which reports a missing mount as a normal credential
        outcome.

        This checks the *value* only. A failure that depends on process state
        rather than on the value -- a valid relative directory resolved while the
        working directory is gone, say -- is invisible here and is guarded at the
        resolution site in :meth:`_resolve_secret_path` instead.

        Args:
            provider_id: Only used to attribute the resulting error; the
                configuration fault is not caused by it.

        Returns:
            The configured ``secrets_dir``, unchanged.

        Raises:
            CredentialBackendError: ``secrets_dir`` is unusable. The message
                describes the configuration fault and never any file content.
        """
        secrets_dir = self._secrets_dir

        if not isinstance(secrets_dir, str) or not secrets_dir:
            raise CredentialBackendError(
                provider_id,
                "configured secrets_dir must be a non-empty string",
            )

        if "\x00" in secrets_dir:
            raise CredentialBackendError(
                provider_id,
                "configured secrets_dir must not contain a NUL character",
            )

        # Same rationale as the provider_id gate: `os.fsencode` applies exactly
        # the conversion the OS layer performs, touches no filesystem, and
        # raises UnicodeEncodeError (a ValueError) for a value the platform
        # cannot encode. Catching ValueError guarantees no variant escapes.
        # The flag mirrors the provider_id gate so the raise happens after the
        # handler has exited, leaving no chained exception carrying the path.
        encodable = True
        try:
            os.fsencode(secrets_dir)
        except ValueError:
            encodable = False

        if not encodable:
            raise CredentialBackendError(
                provider_id,
                "configured secrets_dir is not encodable for this filesystem",
            )

        return secrets_dir

    @staticmethod
    def _validate_provider_id(provider_id: str) -> None:
        """Reject an unsafe ``provider_id`` using string analysis only (INV-1).

        This stage performs **no** filesystem access. Every rejection raises
        ``CredentialBackendError``, so the credential seam's documented
        exception contract holds for all malformed input -- notably an embedded
        NUL or an identifier the filesystem cannot encode (such as a lone
        surrogate), either of which would otherwise reach a path API and
        surface as a bare ``ValueError``. An unsafe id is always rejected
        outright, never rewritten into a "safe" filename.

        Raises:
            CredentialBackendError: the provider_id is not a usable single
                path-safe filename component. The message may name the
                provider_id but never any file content (INV-6).
        """
        # Reject empty, whitespace-only, or non-string identifiers.
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise CredentialBackendError(
                provider_id if isinstance(provider_id, str) else "<non-string>",
                "provider_id must be a non-empty, non-whitespace string",
            )

        # Reject an embedded NUL *before* any filesystem call. Python's path
        # APIs raise ValueError("embedded null byte") for such input, which
        # would escape this seam's CredentialBackendError contract. The NUL is
        # escaped in the message so a raw control byte never reaches a log.
        if "\x00" in provider_id:
            raise CredentialBackendError(
                provider_id.replace("\x00", "\\x00"),
                "provider_id must not contain a NUL character",
            )

        # Reject an identifier the filesystem layer cannot encode, *before* any
        # path API sees it. `os.fsencode` applies exactly the same conversion
        # the OS layer performs (it is pure string-to-bytes encoding and touches
        # no filesystem), so this rejects precisely the identifiers that would
        # otherwise reach `os.path.realpath` and surface as a bare
        # UnicodeEncodeError -- notably a lone surrogate such as "\ud800",
        # which is reachable because upstream config loading accepts any
        # non-empty string as a provider_id (ADR-0017 Decision G).
        #
        # UnicodeEncodeError is a ValueError subclass; catching ValueError
        # guarantees no ValueError variant escapes this seam. Surrogates in the
        # surrogateescape range (U+DC80..U+DCFF) still encode normally and
        # therefore remain accepted -- this adds no new charset policy, it only
        # closes the foreign-exception path.
        encodable = True
        try:
            os.fsencode(provider_id)
        except ValueError:
            encodable = False

        if not encodable:
            # Escape the identifier to pure ASCII for the message: an
            # unencodable value would otherwise break the log/output layer that
            # renders this error, merely relocating the same failure.
            raise CredentialBackendError(
                provider_id.encode("ascii", "backslashreplace").decode("ascii"),
                "provider_id is not encodable for this filesystem",
            )

        # Reject path separators and absolute paths: provider_id must be a
        # single filename component.
        if "/" in provider_id or "\\" in provider_id or os.path.isabs(provider_id):
            raise CredentialBackendError(
                provider_id,
                "provider_id must be a single path-safe filename component",
            )

        # ADR-0017 Decision G: reject any ".." *path segment*. Because
        # separators are rejected above, provider_id is already a single
        # component here; the split is kept explicit so this states the segment
        # rule itself rather than depending on the ordering of that check.
        #
        # A segment equal to ".." is parent-directory traversal. An identifier
        # that merely *contains* two adjacent dots (e.g. "a..b", "foo..bar") is
        # an ordinary filename with no traversal meaning and is accepted --
        # rejecting it would exceed what Decision G requires.
        if any(
            segment == ".." for segment in provider_id.replace("\\", "/").split("/")
        ):
            raise CredentialBackendError(
                provider_id,
                "provider_id must not contain a '..' path segment",
            )

    @staticmethod
    def _is_contained(resolved_dir: str, resolved_target: str) -> bool:
        """Return True iff ``resolved_target`` is ``resolved_dir`` or beneath it.

        Uses ``os.path.commonpath`` for correct component-wise containment, so
        ``/run/secrets`` does not accidentally "contain" ``/run/secrets-evil``.
        """
        if resolved_target == resolved_dir:
            # The directory itself is not a credential; let it through here so
            # the regular-file check can reject it with a clearer message.
            return True
        try:
            return (
                os.path.commonpath([resolved_dir, resolved_target]) == resolved_dir
            )
        except ValueError:
            # Different drives / mixed path kinds -- treat as an escape.
            return False

    @staticmethod
    def _strip_single_trailing_newline(text: str) -> str:
        """Strip exactly one trailing newline (LF or CRLF).

        Mounted secret files commonly carry a single trailing newline (e.g.
        ``echo secret > file``). Exactly one trailing newline is removed; all
        other content -- including any other whitespace -- is preserved as-is.

        ``text`` is the decoded credential, so this frame is scrubbed on exit
        for the same reason :meth:`get` is (INV-6). The string operations here
        do not themselves raise, but an asynchronous interruption (a signal
        handler raising KeyboardInterrupt) can land on any bytecode boundary
        inside this frame; without the scrub, that exception's traceback would
        carry the plaintext in ``text``.
        """
        try:
            if text.endswith("\r\n"):
                return text[:-2]
            if text.endswith("\n"):
                return text[:-1]
            return text
        finally:
            # Safe for the return paths above: the return value is already on
            # the interpreter's value stack before `finally` runs.
            del text

    @staticmethod
    def _os_error_reason(exc: OSError) -> str:
        """Return a short, secret-free reason string for an OS error."""
        return exc.strerror or exc.__class__.__name__

    # ------------------------------------------------------------------
    # Diagnostics -- never expose secret values (INV-6)
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        # Shows only configuration (the mount directory), never a secret value.
        return f"ContainerFileCredentialBackend(secrets_dir={self._secrets_dir!r})"


__all__ = [
    "ContainerFileCredentialBackend",
    "MAX_CREDENTIAL_FILE_SIZE_BYTES",
    "DEFAULT_SECRETS_DIR",
]
