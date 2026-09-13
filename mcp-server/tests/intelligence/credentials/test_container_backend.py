"""Unit and security tests for ContainerFileCredentialBackend (ADR-0017 Phase 5B).

These tests exercise the file-mounted, read-only credential backend against the
security invariants it must uphold:

* INV-1  provider_id path safety and resolved-path containment.
* INV-3  read-only contract (set / delete refused).
* INV-5  bounded, regular-file reads.
* INV-6  secret values never surface in repr / str / exceptions -- including in
         any frame local or chained exception still reachable through a raised
         error's traceback.

Configuration safety is covered alongside them: a ``secrets_dir`` no path API can
accept must fail closed as a credential error rather than as a foreign
``TypeError``/``ValueError``.

All tests use temporary directories -- never the real ``/run/secrets`` -- and a
distinctive sentinel value so any accidental leak is easy to detect.
"""

from __future__ import annotations

import errno
import os
import sys
import tempfile
import traceback
import unittest
from typing import Callable
from unittest import mock

from app.intelligence.credentials.base import (
    CredentialBackend,
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialStore,
    CredentialStoreError,
    InMemoryCredentialBackend,
)
from app.intelligence.credentials.container_backend import (
    DEFAULT_SECRETS_DIR,
    MAX_CREDENTIAL_FILE_SIZE_BYTES,
    ContainerFileCredentialBackend,
)
from app.intelligence.providers.credential import ProviderCredential

# A distinctive, obviously-fake sentinel. If this string ever appears in a
# repr, str, or exception message, an INV-6 leak has occurred.
TEST_SECRET_DO_NOT_LEAK = "TEST_SECRET_DO_NOT_LEAK-sk-0000-abcdEFGH"


def _symlinks_supported() -> bool:
    """Return True if this environment can create symlinks in a temp dir."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, "link")
            target = os.path.join(tmp, "target")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("x")
            os.symlink(target, link)
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


def _running_as_root() -> bool:
    """Return True if the current process can bypass file permission bits."""
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


def _fs_encodable(value: str) -> bool:
    """Return True if this platform's filesystem layer can encode ``value``.

    Lone surrogates are unencodable under the POSIX default
    (``utf-8``/``surrogateescape``) but *are* encodable on Windows, which uses
    ``surrogatepass``. Tests that assert the identifier is refused before any
    filesystem call therefore gate on this capability rather than on the OS
    name: only where the platform cannot encode the value is the pure-string
    rejection the reachable code path.
    """
    try:
        os.fsencode(value)
    except ValueError:
        return False
    return True


# Identifiers containing a lone surrogate: unencodable for the POSIX filesystem
# layer, yet accepted by upstream config loading (ADR-0017 Decision G).
LONE_SURROGATE_IDS = ["\ud800", "a\ud800b", "\udfff"]
SURROGATES_UNENCODABLE = not any(_fs_encodable(v) for v in LONE_SURROGATE_IDS)

# The backend module name. Used by the walker's anti-vacuity self-check to
# build a traceback frame that the backend module owns.
BACKEND_MODULE = ContainerFileCredentialBackend.__module__

# The credential-abstraction module (`base.py`). Needed to state a *partial* fix
# precisely: the backend frame can be clean while a caller frame in a module
# outside this phase's authorized scope is not.
BASE_MODULE = CredentialStore.__module__

# This test module's own name. The exception walker inspects the locals of
# every traceback frame EXCEPT the test harness's own: a test method
# legitimately holds the fixture bytes it just wrote, which would be a false
# positive about the product. Excluding only the harness -- rather than
# admitting only the backend -- keeps ``base.py`` and anything else the backend
# calls in scope, so a leak landing outside the backend module is still caught.
TEST_MODULE = __name__

SYMLINKS = _symlinks_supported()
IS_ROOT = _running_as_root()
IS_WINDOWS = os.name == "nt"


def _fs_accepts_filename(name: str) -> bool:
    """Return True if a file can actually be created with ``name``.

    :func:`_fs_encodable` only asks whether the *codec* can convert the string;
    the filesystem may still refuse the resulting bytes. APFS and HFS+ reject
    filenames that are not valid UTF-8 (``EILSEQ``), while ext4 and tmpfs accept
    any non-NUL bytes. A test that writes such a file must gate on this stronger
    probe, otherwise it fails inside fixture setup and is reported as an ERROR
    rather than as a meaningful assertion failure.
    """
    if not _fs_encodable(name):
        return False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, name)
            with open(path, "wb") as handle:
                handle.write(b"x")
            os.remove(path)
        return True
    except (OSError, ValueError):
        return False


# A surrogateescape-range identifier (U+DC80..U+DCFF) encodes on POSIX and
# addresses real files whose names are not valid UTF-8. Reading one end-to-end
# needs a filesystem that will store such a name; asserting the backend
# *accepts* the identifier needs no filesystem at all, so the two are separate.
SURROGATE_ESCAPE_ID = "\udc80"
FS_ACCEPTS_SURROGATE_ESCAPE_NAME = _fs_accepts_filename(SURROGATE_ESCAPE_ID)


def _render(value: object) -> str:
    """Render ``value`` for leak scanning, defeating bytes escaping.

    ``repr`` of a bytes object escapes non-ASCII as ``\\xNN``, so a plain
    substring search for a non-ASCII secret would miss it. Any bytes value
    reachable one level down -- which is where frame locals and exception args
    live -- is therefore also appended as lossily-decoded text.
    """
    parts = [repr(value)]
    candidates: list[object] = [value]
    if isinstance(value, dict):
        candidates.extend(value.values())
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates.extend(value)
    for item in candidates:
        if isinstance(item, (bytes, bytearray)):
            parts.append(bytes(item).decode("utf-8", "replace"))
    return "".join(parts)


def _make_backend_frame_raiser() -> Callable[[object], None]:
    """Build a callable whose frame claims the backend module as its globals.

    Pinning the walker's frame-locals branch needs a traceback frame that the
    walker will actually inspect *and* that holds a planted secret. A helper
    defined in this test module cannot serve, because the walker skips the test
    harness's own frames by design. Compiling the helper against a copy of the
    backend module's globals gives its frame the backend's ``__name__``, which
    is exactly the condition that branch keys on.
    """
    namespace = dict(sys.modules[BACKEND_MODULE].__dict__)
    exec(  # noqa: S102 - deliberate: builds a frame owned by the backend module
        "def _raise_holding_secret(planted_secret):\n"
        "    raise RuntimeError('synthetic failure inside the backend module')\n",
        namespace,
    )
    return namespace["_raise_holding_secret"]


def _strip_raising_after_decode(text: str) -> str:
    """Stand-in for the strip helper that fails once the plaintext exists.

    Injects a fault at the one point in ``get`` reached with the decoded
    credential bound: the call that consumes it. Defined in *this* module on
    purpose, so the walker skips this frame and the assertion is only about what
    the backend's own frame retained. A ``mock.Mock`` side effect would not do:
    the mock records its call arguments, so the secret would be reachable
    through the test double rather than through the product.
    """
    raise RuntimeError("synthetic post-decode failure")


class _EndswithRaisingStr(str):
    """A ``str`` whose ``endswith`` raises, to fault-inject inside the helper.

    ``_strip_single_trailing_newline`` has no statement that can fail on its
    own, yet its frame holds the plaintext, so an asynchronous interruption
    landing on any bytecode boundary inside it would put the credential on a
    traceback. Driving the failure from the argument's own method keeps the test
    mock-free and runs the real helper body.
    """

    def endswith(self, *args: object, **kwargs: object) -> bool:  # type: ignore[override]
        raise RuntimeError("synthetic interruption inside the strip helper")


class _BackendTestBase(unittest.TestCase):
    """Common temp-directory fixture and helpers for the backend tests."""

    def setUp(self) -> None:
        self.secrets_dir = tempfile.mkdtemp(prefix="cfcb_secrets_")
        self.addCleanup(self._cleanup_dir, self.secrets_dir)
        self.backend = ContainerFileCredentialBackend(self.secrets_dir)

    @staticmethod
    def _cleanup_dir(path: str) -> None:
        # Restore permissions on any locked-down test file so the tree can be
        # removed, then delete it. Errors are ignored -- this is only cleanup.
        for root, dirs, files in os.walk(path):
            for name in dirs + files:
                try:
                    os.chmod(os.path.join(root, name), 0o700)
                except OSError:
                    pass
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
        import shutil

        shutil.rmtree(path, ignore_errors=True)

    def _write_secret(self, name: str, data: bytes) -> str:
        """Write raw bytes to ``<secrets_dir>/<name>`` and return the path."""
        path = os.path.join(self.secrets_dir, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    @staticmethod
    def _capture(func: Callable[..., object], *args: object) -> BaseException:
        """Call ``func`` and return the exception it raised, traceback intact.

        ``assertRaises`` is unusable for INV-6 reachability checks: its context
        manager calls ``traceback.clear_frames(tb)`` and then stores
        ``exc_value.with_traceback(None)``, so ``ctx.exception.__traceback__``
        is ``None`` and every frame local is gone before the test can look. An
        assertion about frame locals made through ``assertRaises`` is therefore
        vacuous by construction. A bare ``except`` keeps the traceback and its
        frames attached, which is the surface these tests exist to inspect.
        """
        try:
            func(*args)
        except BaseException as exc:  # noqa: BLE001 - the exception IS the subject
            return exc
        raise AssertionError("expected the call to raise, but it returned")

    @staticmethod
    def _reachable_exception_payload(exc: BaseException) -> str:
        """Serialize everything a consumer could reach from ``exc``.

        Walks the whole exception graph -- ``__cause__`` and ``__context__``,
        transitively -- and for each node collects its ``str``, ``repr``,
        ``args``, instance ``__dict__``, any ``__notes__``, the ``object``
        attribute that Unicode errors use to carry their offending input, and
        the locals of every frame in its traceback other than this test
        module's own. This is the surface an error reporter, debugger, or
        structured log serializer can actually observe, which is broader than
        what the default traceback formatter prints.

        Frames are filtered by *excluding the harness* rather than by admitting
        only the backend, so a leak that lands in ``base.py`` or any other
        module the backend calls is still detected.
        """
        parts: list[str] = []
        seen: set[int] = set()
        queue: list[BaseException | None] = [exc]
        while queue:
            current = queue.pop()
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))
            parts.extend(
                (
                    str(current),
                    repr(current),
                    _render(current.args),
                    _render(getattr(current, "__dict__", {})),
                    _render(list(getattr(current, "__notes__", []))),
                    _render(getattr(current, "object", "")),
                )
            )
            tb = current.__traceback__
            while tb is not None:
                frame = tb.tb_frame
                if frame.f_globals.get("__name__") != TEST_MODULE:
                    parts.append(_render(frame.f_locals))
                tb = tb.tb_next
            queue.append(current.__cause__)
            queue.append(current.__context__)
        return "".join(parts)

    @staticmethod
    def _frame_locals_by_module(exc: BaseException) -> dict[str, str]:
        """Map module name -> rendered frame locals for each traceback frame.

        :meth:`_reachable_exception_payload` answers "is the secret reachable at
        all". This answers "reachable from *whose* frame", which is the only way
        to state a partial fix honestly: one module's frames can be proven clean
        while another module's -- outside the authorized change scope -- are
        demonstrably not. No frame is filtered out here; the caller selects the
        module it means to assert about.
        """
        rendered: dict[str, str] = {}
        tb = exc.__traceback__
        while tb is not None:
            frame = tb.tb_frame
            module = str(frame.f_globals.get("__name__"))
            rendered[module] = rendered.get(module, "") + _render(frame.f_locals)
            tb = tb.tb_next
        return rendered


class HappyPathReadTests(_BackendTestBase):
    """INV-5 / core contract: a valid secret file is read correctly."""

    def test_reads_value_with_no_trailing_newline(self) -> None:
        self._write_secret("openai", TEST_SECRET_DO_NOT_LEAK.encode("utf-8"))
        self.assertEqual(self.backend.get("openai"), TEST_SECRET_DO_NOT_LEAK)

    def test_strips_exactly_one_trailing_lf(self) -> None:
        self._write_secret(
            "openai", (TEST_SECRET_DO_NOT_LEAK + "\n").encode("utf-8")
        )
        self.assertEqual(self.backend.get("openai"), TEST_SECRET_DO_NOT_LEAK)

    def test_strips_one_trailing_crlf(self) -> None:
        self._write_secret(
            "openai", (TEST_SECRET_DO_NOT_LEAK + "\r\n").encode("utf-8")
        )
        self.assertEqual(self.backend.get("openai"), TEST_SECRET_DO_NOT_LEAK)

    def test_preserves_second_trailing_newline(self) -> None:
        # Only ONE trailing newline is stripped; a second is real content.
        self._write_secret(
            "openai", (TEST_SECRET_DO_NOT_LEAK + "\n\n").encode("utf-8")
        )
        self.assertEqual(
            self.backend.get("openai"), TEST_SECRET_DO_NOT_LEAK + "\n"
        )

    def test_preserves_trailing_space_before_newline(self) -> None:
        # Whitespace that is not the single trailing newline is preserved.
        self._write_secret("openai", b"secret-with-space \n")
        self.assertEqual(self.backend.get("openai"), "secret-with-space ")

    def test_accepts_valid_identifier_shapes(self) -> None:
        # Identifiers with hyphens, underscores, single dots, and mixed case
        # are legitimate single filename components and must be accepted.
        valid_ids = [
            "openai",
            "anthropic-cloud",
            "provider_with_underscores",
            "provider.with.single.dots",
            "MixedCase123",
        ]
        for provider_id in valid_ids:
            with self.subTest(provider_id=provider_id):
                self._write_secret(
                    provider_id, TEST_SECRET_DO_NOT_LEAK.encode("utf-8")
                )
                self.assertEqual(
                    self.backend.get(provider_id), TEST_SECRET_DO_NOT_LEAK
                )

    def test_custom_secrets_dir_is_used(self) -> None:
        self._write_secret("custom-provider", TEST_SECRET_DO_NOT_LEAK.encode("utf-8"))

        self.assertEqual(
            self.backend.get("custom-provider"),
            TEST_SECRET_DO_NOT_LEAK,
        )


class ProviderIdPathSafetyTests(_BackendTestBase):
    """INV-1: provider_id is validated; unsafe ids are rejected, not rewritten."""

    def _assert_rejected(self, provider_id: str) -> None:
        with self.assertRaises(CredentialBackendError) as ctx:
            self.backend.get(provider_id)
        # The exception may name the provider but must not leak file content.
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(ctx.exception))

    def test_empty_string_rejected(self) -> None:
        self._assert_rejected("")

    def test_whitespace_only_rejected(self) -> None:
        self._assert_rejected("   ")

    def test_forward_slash_rejected(self) -> None:
        self._assert_rejected("nested/key")

    def test_backslash_rejected(self) -> None:
        self._assert_rejected("nested\\key")

    def test_parent_dir_token_rejected(self) -> None:
        self._assert_rejected("..")

    def test_parent_dir_traversal_rejected(self) -> None:
        self._assert_rejected("../../etc/passwd")

    def test_absolute_path_rejected(self) -> None:
        self._assert_rejected("/etc/passwd")

    def test_parent_dir_segment_forms_rejected(self) -> None:
        # ADR-0017 Decision G rejects any ".." *path segment*. Every form below
        # contains one, either as the whole identifier or as a component of a
        # traversal expression (including Windows-style separators, which are
        # refused on every platform).
        traversal_ids = [
            "..",
            "../foo",
            "foo/../bar",
            "../",
            "foo/..",
            "..\\foo",
            "foo\\..\\bar",
            "....//foo",
        ]
        for provider_id in traversal_ids:
            with self.subTest(provider_id=provider_id):
                self._assert_rejected(provider_id)

    def test_double_dot_inside_single_component_is_accepted(self) -> None:
        # A ".." *segment* is traversal; two adjacent dots *inside* one
        # filename component are not. Identifiers like "a..b" are ordinary
        # single-component filenames and must be accepted -- rejecting them on
        # the substring alone would exceed what Decision G requires.
        accepted_ids = ["a..b", "foo..bar"]
        for provider_id in accepted_ids:
            with self.subTest(provider_id=provider_id):
                self._write_secret(
                    provider_id, TEST_SECRET_DO_NOT_LEAK.encode("utf-8")
                )
                # Acceptance means the real secret is actually readable from
                # the corresponding file, not merely that no error was raised.
                self.assertEqual(
                    self.backend.get(provider_id), TEST_SECRET_DO_NOT_LEAK
                )

    def test_nul_byte_rejected_as_backend_error_without_filesystem_access(
        self,
    ) -> None:
        # An embedded NUL must be refused through the credential exception
        # hierarchy at the provider-id validation boundary. Python's path APIs
        # raise ValueError("embedded null byte") for such input; that must never
        # escape this seam.
        def _fail_if_called(*_args: object, **_kwargs: object) -> object:
            raise AssertionError(
                "provider_id validation must not touch the filesystem"
            )

        # Guard every filesystem entry point the read path uses, proving this
        # rejection is pure string validation.
        with mock.patch.object(os, "stat", _fail_if_called), mock.patch.object(
            os.path, "realpath", _fail_if_called
        ), mock.patch("builtins.open", _fail_if_called):
            with self.assertRaises(CredentialBackendError) as ctx:
                self.backend.get("a\x00b")

        exc = ctx.exception
        # The seam's own exception type -- not a bare ValueError.
        self.assertNotIsInstance(exc, ValueError)
        message = str(exc)
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, message)
        # No raw control byte is propagated into the message (log safety).
        self.assertNotIn("\x00", message)

    @unittest.skipUnless(
        SURROGATES_UNENCODABLE,
        "platform filesystem encoding accepts lone surrogates",
    )
    def test_lone_surrogate_provider_id_rejected_as_backend_error(self) -> None:
        # A lone surrogate survives every other string rule (non-empty, no NUL,
        # no separator, no ".." segment) but cannot be encoded by this
        # platform's filesystem layer. Left unchecked it reaches
        # os.path.realpath and surfaces as a bare UnicodeEncodeError -- a
        # ValueError, not a CredentialStoreError -- so it would bypass the
        # configuration-error mapping documented on the CredentialBackend
        # contract. Such an id is reachable because upstream config loading
        # constrains no charset (ADR-0017 Decision G).
        #
        # Gated on the capability probe, like its sibling below: where the
        # platform CAN encode lone surrogates (Windows uses surrogatepass) the
        # encodability gate deliberately does not fire, and the resulting error
        # class is then decided by the OS rather than by the code under test.
        # The contract that holds on every platform is asserted separately.
        for provider_id in LONE_SURROGATE_IDS:
            with self.subTest(provider_id=repr(provider_id)):
                with self.assertRaises(CredentialBackendError) as ctx:
                    self.backend.get(provider_id)
                exc = ctx.exception
                # The seam's own type, never a raw Unicode/ValueError.
                self.assertNotIsInstance(exc, ValueError)
                self.assertNotIsInstance(exc, UnicodeEncodeError)
                message = str(exc)
                self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, message)
                # The message must itself be encodable, or rendering this error
                # to a log would merely relocate the same failure.
                message.encode("utf-8")

    def test_lone_surrogate_provider_id_never_raises_foreign_exception(self) -> None:
        # The platform-independent half of the contract above, so Windows keeps
        # meaningful coverage instead of only a skip. Whether or not the
        # encodability gate fires, `get` must fail through the credential
        # exception hierarchy -- never a bare ValueError/UnicodeEncodeError and
        # never a raw OSError.
        #
        # Which CredentialStoreError subclass is raised is deliberately NOT
        # asserted: where the platform encodes lone surrogates the identifier
        # legitimately reaches the filesystem, and "no such file" is a correct
        # answer there. Asserting the subclass would pin this test to a Win32
        # error code rather than to the backend's behaviour.
        for provider_id in LONE_SURROGATE_IDS:
            with self.subTest(provider_id=repr(provider_id)):
                with self.assertRaises(CredentialStoreError) as ctx:
                    self.backend.get(provider_id)
                exc = ctx.exception
                self.assertNotIsInstance(exc, ValueError)
                self.assertNotIsInstance(exc, OSError)

    @unittest.skipUnless(
        SURROGATES_UNENCODABLE,
        "platform filesystem encoding accepts lone surrogates",
    )
    def test_lone_surrogate_rejected_without_filesystem_access(self) -> None:
        # Where the platform cannot encode the identifier, the rejection must
        # happen in pure string validation -- before any filesystem call.
        def _fail_if_called(*_args: object, **_kwargs: object) -> object:
            raise AssertionError(
                "provider_id validation must not touch the filesystem"
            )

        with mock.patch.object(os, "stat", _fail_if_called), mock.patch.object(
            os.path, "realpath", _fail_if_called
        ), mock.patch("builtins.open", _fail_if_called):
            for provider_id in LONE_SURROGATE_IDS:
                with self.subTest(provider_id=repr(provider_id)):
                    with self.assertRaises(CredentialBackendError):
                        self.backend.get(provider_id)

    def test_surrogateescape_range_id_accepted_by_validation(self) -> None:
        # Guards against over-rejecting: surrogates in the surrogateescape
        # range (U+DC80..U+DCFF) DO encode, and already address real files whose
        # names are not valid UTF-8. Closing the foreign-exception hole must not
        # silently introduce a new charset policy that breaks them.
        #
        # This half touches no filesystem -- it asserts the validation stage
        # accepts the identifier -- so it runs on every platform and can never
        # be skipped. That keeps the over-rejection guard (the actual production
        # guarantee) unconditional even where the filesystem refuses the name.
        self.assertTrue(_fs_encodable(SURROGATE_ESCAPE_ID))
        ContainerFileCredentialBackend._validate_provider_id(SURROGATE_ESCAPE_ID)

    @unittest.skipUnless(
        FS_ACCEPTS_SURROGATE_ESCAPE_NAME,
        "filesystem refuses filenames that are not valid UTF-8",
    )
    def test_surrogateescape_range_id_read_end_to_end(self) -> None:
        # The end-to-end half needs a filesystem that will actually store a name
        # whose bytes are not valid UTF-8. ext4 and tmpfs do; APFS and HFS+
        # return EILSEQ. Gated on a real create-a-file probe rather than on the
        # codec check, so an unsupported filesystem skips here instead of
        # erroring inside fixture setup.
        self._write_secret(
            SURROGATE_ESCAPE_ID, TEST_SECRET_DO_NOT_LEAK.encode("utf-8")
        )
        self.assertEqual(
            self.backend.get(SURROGATE_ESCAPE_ID), TEST_SECRET_DO_NOT_LEAK
        )

    @unittest.skipUnless(SYMLINKS, "symlinks not supported here")
    @unittest.skipIf(IS_WINDOWS, "POSIX symlink semantics assumed")
    def test_symlink_escaping_secrets_dir_rejected(self) -> None:
        # A symlink inside secrets_dir that points OUTSIDE must be refused,
        # and the outside file's content must never be returned or leaked.
        outside_dir = tempfile.mkdtemp(prefix="cfcb_outside_")
        self.addCleanup(self._cleanup_dir, outside_dir)
        outside_file = os.path.join(outside_dir, "outside_secret")
        with open(outside_file, "w", encoding="utf-8") as handle:
            handle.write(TEST_SECRET_DO_NOT_LEAK)

        os.symlink(outside_file, os.path.join(self.secrets_dir, "evil"))

        with self.assertRaises(CredentialBackendError) as ctx:
            self.backend.get("evil")
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(ctx.exception))

    @unittest.skipUnless(SYMLINKS, "symlinks not supported here")
    @unittest.skipIf(IS_WINDOWS, "POSIX symlink semantics assumed")
    def test_sibling_prefix_dir_is_not_treated_as_contained(self) -> None:
        # Guards against a naive string-prefix containment check:
        # ``/base/secrets`` must NOT be considered to contain
        # ``/base/secrets-evil``.
        base = tempfile.mkdtemp(prefix="cfcb_base_")
        self.addCleanup(self._cleanup_dir, base)
        secrets = os.path.join(base, "secrets")
        sibling = os.path.join(base, "secrets-evil")
        os.mkdir(secrets)
        os.mkdir(sibling)
        with open(os.path.join(sibling, "key"), "w", encoding="utf-8") as handle:
            handle.write(TEST_SECRET_DO_NOT_LEAK)
        # Relative symlink from inside `secrets` into the sibling directory.
        os.symlink(
            os.path.join("..", "secrets-evil", "key"),
            os.path.join(secrets, "key"),
        )

        backend = ContainerFileCredentialBackend(secrets)
        with self.assertRaises(CredentialBackendError) as ctx:
            backend.get("key")
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(ctx.exception))

    @unittest.skipUnless(SYMLINKS, "symlinks not supported here")
    @unittest.skipIf(IS_WINDOWS, "POSIX symlink semantics assumed")
    def test_internal_symlink_within_secrets_dir_is_accepted(self) -> None:
        # Emulates a Kubernetes projected-secret layout: a dot-prefixed data
        # directory plus a symlink for the provider that stays inside
        # secrets_dir. Such internal symlinks must be followed and accepted.
        data_dir = os.path.join(self.secrets_dir, "..data_real")
        os.mkdir(data_dir)
        with open(os.path.join(data_dir, "openai"), "w", encoding="utf-8") as handle:
            handle.write(TEST_SECRET_DO_NOT_LEAK)
        os.symlink(
            os.path.join("..data_real", "openai"),
            os.path.join(self.secrets_dir, "openai"),
        )

        # provider_id "openai" contains no traversal; the ".." only appears in
        # the internal directory name, which the backend does not inspect.
        self.assertEqual(self.backend.get("openai"), TEST_SECRET_DO_NOT_LEAK)


class FileValidationTests(_BackendTestBase):
    """INV-5: existence, regular-file, readability, and size bounds."""

    def test_missing_file_raises_not_found(self) -> None:
        with self.assertRaises(CredentialNotFoundError) as ctx:
            self.backend.get("absent")
        self.assertEqual(ctx.exception.provider_id, "absent")

    def test_directory_target_rejected(self) -> None:
        os.mkdir(os.path.join(self.secrets_dir, "adir"))
        with self.assertRaises(CredentialBackendError) as ctx:
            self.backend.get("adir")
        self.assertIn("regular file", str(ctx.exception))

    def test_oversized_file_rejected(self) -> None:
        backend = ContainerFileCredentialBackend(
            self.secrets_dir, max_file_size_bytes=16
        )
        # Content larger than the cap; also uses the sentinel to double-check
        # that an oversize error never echoes file content.
        self._write_secret("openai", TEST_SECRET_DO_NOT_LEAK.encode("utf-8"))
        with self.assertRaises(CredentialBackendError) as ctx:
            backend.get("openai")
        self.assertIn("maximum allowed size", str(ctx.exception))
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(ctx.exception))

    def test_file_at_exact_size_limit_is_read(self) -> None:
        backend = ContainerFileCredentialBackend(
            self.secrets_dir, max_file_size_bytes=16
        )
        exact = b"0123456789abcdef"  # exactly 16 bytes, no trailing newline
        self.assertEqual(len(exact), 16)
        self._write_secret("openai", exact)
        self.assertEqual(backend.get("openai"), exact.decode("utf-8"))

    def test_file_one_byte_over_limit_rejected(self) -> None:
        backend = ContainerFileCredentialBackend(
            self.secrets_dir, max_file_size_bytes=16
        )
        self._write_secret("openai", b"0123456789abcdefX")  # 17 bytes
        with self.assertRaises(CredentialBackendError):
            backend.get("openai")

    def test_non_utf8_file_rejected(self) -> None:
        self._write_secret("openai", b"\xff\xfe\xff\xfe")
        with self.assertRaises(CredentialBackendError) as ctx:
            self.backend.get("openai")
        self.assertIn("UTF-8", str(ctx.exception))

    def test_oversize_error_has_no_reachable_secret_bearing_frame(self) -> None:
        # INV-6 on the *other* raise reachable while the read buffer is bound.
        #
        # Two raises in `get` fire after the file has been read: this post-read
        # size re-check and the non-UTF-8 rejection. Scrubbing only the latter
        # left the credential in this frame's locals, reachable through
        # `exc.__traceback__` -- the same leak class, on the branch nobody
        # tested. This path fires whenever `st_size` understated the real
        # content: a file that grew between `stat` and `read`, or a regular file
        # whose reported size is 0 (procfs/sysfs, stale network metadata). The
        # patch below reproduces that under-report deterministically.
        # The cap must exceed the sentinel's length. The read is bounded to
        # `cap + 1` bytes, so with a small cap the retained buffer is only a
        # prefix that no longer contains the whole sentinel -- and the leak
        # assertion below would pass vacuously even with the scrub removed.
        # Confirmed by mutation: with the scrub reverted this test fails at
        # cap=64 and wrongly passes at cap=16.
        cap = 64
        self.assertGreater(cap, len(TEST_SECRET_DO_NOT_LEAK))
        payload = TEST_SECRET_DO_NOT_LEAK.encode("utf-8") * 8
        path = self._write_secret("openai", payload)
        self.assertGreater(len(payload), cap)
        backend = ContainerFileCredentialBackend(
            self.secrets_dir, max_file_size_bytes=cap
        )
        real_stat = os.stat
        target = os.path.realpath(path)

        class _UnderReportingStat:
            """A stat result claiming size 0 for a file that has content."""

            def __init__(self, st_mode: int) -> None:
                self.st_mode = st_mode
                self.st_size = 0

        def _stat_under_reporting_size(item, *args, **kwargs):  # type: ignore[no-untyped-def]
            result = real_stat(item, *args, **kwargs)
            if isinstance(item, (str, bytes, os.PathLike)) and (
                os.path.realpath(os.fsdecode(item)) == target
            ):
                return _UnderReportingStat(result.st_mode)
            return result

        with mock.patch.object(os, "stat", _stat_under_reporting_size):
            # Captured with a bare `except`, not `assertRaises`: the latter
            # clears the traceback frames this assertion must inspect.
            exc = self._capture(backend.get, "openai")

        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIn("maximum allowed size", str(exc))
        self.assertIsNone(exc.__cause__)
        self.assertIsNone(exc.__context__)
        # The frames really are present, so the check below is not vacuous.
        self.assertIsNotNone(exc.__traceback__)
        # The decisive assertion: no frame local, chained exception, or payload
        # anywhere in the reachable graph still holds the credential bytes.
        self.assertNotIn(
            TEST_SECRET_DO_NOT_LEAK, self._reachable_exception_payload(exc)
        )
        rendered = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, rendered)

    def test_non_utf8_error_has_no_reachable_secret_bearing_context(self) -> None:
        # A UnicodeDecodeError carries the offending input in its `object`
        # attribute -- here, the raw credential bytes. Suppressing the *render*
        # is not enough: `raise ... from None` leaves `__context__` bound, so a
        # consumer walking the exception chain can still recover the credential.
        # The error crossing this seam must therefore have no secret-bearing
        # node anywhere in its reachable graph (INV-6).
        payload = TEST_SECRET_DO_NOT_LEAK.encode("utf-8") + b"\xff"
        self._write_secret("openai", payload)

        # Captured with a bare `except`, not `assertRaises`: the latter clears
        # the traceback frames, which would make the frame-local half of this
        # assertion vacuous.
        exc = self._capture(self.backend.get, "openai")

        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIn("UTF-8", str(exc))
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(exc))
        # No chained exception at all -- neither explicit nor implicit. This is
        # strictly stronger than __suppress_context__, which only hides a
        # context that is still programmatically reachable.
        self.assertIsNone(exc.__cause__)
        self.assertIsNone(exc.__context__)
        # The frames really are present, so the check below is not vacuous.
        self.assertIsNotNone(exc.__traceback__)
        # Nothing reachable from the exception carries the raw bytes: no args,
        # no `object` attribute, and no frame local in the traceback.
        self.assertNotIn(
            TEST_SECRET_DO_NOT_LEAK, self._reachable_exception_payload(exc)
        )
        # The default traceback render stays clean too.
        rendered = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, rendered)
        # The strict UTF-8 policy is unchanged: no fallback decode happened.
        self.assertNotIsInstance(exc, UnicodeDecodeError)

    def test_close_failure_after_read_leaves_no_reachable_raw_buffer(self) -> None:
        # The read's own `except` handlers are reachable with the buffer already
        # bound: `handle.read(...)` can succeed and the `with` block's `__exit__`
        # can then fail, because POSIX permits `close()` to report a deferred
        # error (EIO/ENOSPC on network, FUSE, and projected mounts). Control
        # enters `except OSError` with `raw` holding the full credential.
        #
        # An earlier revision opened the scrub region *after* the read finished,
        # so this handler ran outside it and put the credential on the traceback.
        # The cap must exceed the sentinel length or the retained buffer would be
        # a short prefix and the assertion would pass vacuously (see the
        # oversize test for the same trap).
        cap = 4096
        self.assertGreater(cap, len(TEST_SECRET_DO_NOT_LEAK))
        backend = ContainerFileCredentialBackend(
            self.secrets_dir, max_file_size_bytes=cap
        )
        path = self._write_secret(
            "openai", TEST_SECRET_DO_NOT_LEAK.encode("utf-8")
        )
        target = os.path.realpath(path)
        real_open = open

        class _FailingCloseFile:
            """Wraps a real file object and fails only on context exit."""

            def __init__(self, handle: object) -> None:
                self._handle = handle

            def __enter__(self) -> object:
                return self

            def read(self, *args: object, **kwargs: object) -> bytes:
                return self._handle.read(*args, **kwargs)  # type: ignore[attr-defined]

            def __exit__(self, *exc_info: object) -> bool:
                self._handle.close()  # type: ignore[attr-defined]
                raise OSError(errno.EIO, "Input/output error")

        def _open_failing_close(item, *args, **kwargs):  # type: ignore[no-untyped-def]
            handle = real_open(item, *args, **kwargs)
            if isinstance(item, (str, bytes, os.PathLike)) and (
                os.path.realpath(os.fsdecode(item)) == target
            ):
                return _FailingCloseFile(handle)
            return handle

        with mock.patch("builtins.open", _open_failing_close):
            exc = self._capture(backend.get, "openai")

        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIn("cannot read secret file", str(exc))
        # The failure really came from the post-read close, so the buffer really
        # was bound when the handler ran -- otherwise this test proves nothing.
        self.assertIsNotNone(exc.__context__)
        self.assertIsInstance(exc.__context__, OSError)
        self.assertIsNotNone(exc.__traceback__)
        self.assertNotIn(
            TEST_SECRET_DO_NOT_LEAK, self._reachable_exception_payload(exc)
        )
        rendered = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, rendered)

    def test_failure_after_decode_leaves_no_reachable_plaintext(self) -> None:
        # Covers the second hole the region redesign closed: the decoded
        # plaintext. `decoded` is bound from the successful decode until the
        # function returns, and the previous revision never scrubbed it at all.
        #
        # The fault is injected at the only statement reached in that window --
        # the strip call that consumes the plaintext -- which stands in for any
        # future statement added there, and for an asynchronous interruption
        # landing on a bytecode boundary inside the window.
        self._write_secret("openai", TEST_SECRET_DO_NOT_LEAK.encode("utf-8"))

        with mock.patch.object(
            ContainerFileCredentialBackend,
            "_strip_single_trailing_newline",
            staticmethod(_strip_raising_after_decode),
        ):
            exc = self._capture(self.backend.get, "openai")

        # The injected error propagates as-is: this test is about what the
        # frames retain, not about error mapping.
        self.assertIsInstance(exc, RuntimeError)
        self.assertIsNotNone(exc.__traceback__)
        # `get`'s frame is on this traceback and is inspected by the walker,
        # so a retained `raw` or `decoded` would be found.
        frames = []
        tb = exc.__traceback__
        while tb is not None:
            frames.append(tb.tb_frame.f_globals.get("__name__"))
            tb = tb.tb_next
        self.assertIn(BACKEND_MODULE, frames)
        self.assertNotIn(
            TEST_SECRET_DO_NOT_LEAK, self._reachable_exception_payload(exc)
        )

    def test_strip_helper_failure_leaves_no_reachable_plaintext(self) -> None:
        # The strip helper's own frame holds the plaintext argument. Its body
        # cannot fail by itself, so the failure is driven from the argument's
        # `endswith`, which runs the real helper body and reaches its `finally`.
        exc = self._capture(
            ContainerFileCredentialBackend._strip_single_trailing_newline,
            _EndswithRaisingStr(TEST_SECRET_DO_NOT_LEAK),
        )

        self.assertIsInstance(exc, RuntimeError)
        self.assertIsNotNone(exc.__traceback__)
        self.assertNotIn(
            TEST_SECRET_DO_NOT_LEAK, self._reachable_exception_payload(exc)
        )

    def test_strip_helper_still_returns_correct_values_after_scrub(self) -> None:
        # `del text` in a `finally` must not disturb the return value: it is
        # already on the interpreter's value stack when `finally` runs. Pins the
        # behaviour the scrub could plausibly have broken.
        strip = ContainerFileCredentialBackend._strip_single_trailing_newline
        self.assertEqual(strip("value"), "value")
        self.assertEqual(strip("value\n"), "value")
        self.assertEqual(strip("value\r\n"), "value")
        self.assertEqual(strip("value\n\n"), "value\n")
        self.assertEqual(strip(""), "")

    def test_reachable_exception_payload_helper_detects_a_planted_secret(
        self,
    ) -> None:
        # The graph walker above is only meaningful if it can actually see a
        # secret. Plant one in each surface it claims to cover and confirm it is
        # found, so a passing INV-6 assertion cannot be vacuous.
        marker = TEST_SECRET_DO_NOT_LEAK
        in_args = CredentialBackendError("openai", marker)
        self.assertIn(marker, self._reachable_exception_payload(in_args))

        # Reachable only via __context__ (the exact vector this fix closes).
        try:
            try:
                raise UnicodeDecodeError(
                    "utf-8", marker.encode("utf-8"), 0, 1, "planted"
                )
            except UnicodeDecodeError:
                raise CredentialBackendError("openai", "sanitized")
        except CredentialBackendError as chained:
            self.assertIsNotNone(chained.__context__)
            self.assertIn(marker, self._reachable_exception_payload(chained))

    def test_reachable_exception_payload_detects_secret_in_backend_frame_local(
        self,
    ) -> None:
        # Pins the walker's frame-locals branch -- the one surface the INV-6
        # fixes actually changed, and the only one the planted-secret test above
        # does NOT cover (it plants into `args` and `__context__.object`).
        #
        # Without this pin the branch can be silently disabled -- by a refactor
        # of the module-name filter, say -- and every INV-6 assertion in this
        # file keeps passing while inspecting nothing. Verified: blinding the
        # filter makes this test fail and the others still pass.
        raiser = _make_backend_frame_raiser()

        ascii_marker = TEST_SECRET_DO_NOT_LEAK
        exc = self._capture(raiser, ascii_marker.encode("utf-8"))
        self.assertIsInstance(exc, RuntimeError)
        self.assertIn(
            ascii_marker,
            self._reachable_exception_payload(exc),
            "the walker's frame-locals branch is blind",
        )

        # A non-ASCII secret must also be found: `repr` of bytes escapes it as
        # \\xNN, so a plain substring search over repr alone would miss it.
        non_ascii_marker = "SECRET-Ünïcödé-☂"
        exc = self._capture(raiser, non_ascii_marker.encode("utf-8"))
        self.assertIn(
            non_ascii_marker,
            self._reachable_exception_payload(exc),
            "the walker cannot see a non-ASCII secret inside bytes",
        )

    @unittest.skipIf(IS_WINDOWS, "POSIX permission semantics assumed")
    @unittest.skipIf(IS_ROOT, "root bypasses file permission bits")
    def test_unreadable_file_rejected(self) -> None:
        path = self._write_secret(
            "openai", TEST_SECRET_DO_NOT_LEAK.encode("utf-8")
        )
        os.chmod(path, 0o000)
        try:
            with self.assertRaises(CredentialBackendError) as ctx:
                self.backend.get("openai")
        finally:
            os.chmod(path, 0o600)
        self.assertIn("not readable", str(ctx.exception))
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(ctx.exception))

    def test_unreadable_file_rejected_regardless_of_uid(self) -> None:
        # The chmod-based test above cannot run as root, because root bypasses
        # the permission bits -- so on a root CI runner (the common container
        # default) the PermissionError branch went entirely untested. Injecting
        # the error the kernel would raise covers that branch at any uid, while
        # the chmod test is kept as the real-kernel check where uid permits.
        #
        # The patch is selective by path, following the style of
        # `_stat_under_reporting_size`: every unrelated `open` during the window
        # (imports, fixture I/O) must keep working, or the test would prove
        # nothing about this branch.
        path = self._write_secret(
            "openai", TEST_SECRET_DO_NOT_LEAK.encode("utf-8")
        )
        target = os.path.realpath(path)
        real_open = open

        def _open_denying_target(item, *args, **kwargs):  # type: ignore[no-untyped-def]
            if isinstance(item, (str, bytes, os.PathLike)) and (
                os.path.realpath(os.fsdecode(item)) == target
            ):
                raise PermissionError(errno.EACCES, "Permission denied")
            return real_open(item, *args, **kwargs)

        with mock.patch("builtins.open", _open_denying_target):
            exc = self._capture(self.backend.get, "openai")

        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIn("not readable", str(exc))
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(exc))
        # Fails closed inside the credential hierarchy: the injected
        # PermissionError never escapes as an OSError.
        self.assertNotIsInstance(exc, OSError)
        self.assertIsInstance(exc, CredentialStoreError)


class ReadOnlyContractTests(_BackendTestBase):
    """INV-3: the backend refuses all write operations and never mutates disk."""

    def test_set_raises_backend_error(self) -> None:
        with self.assertRaises(CredentialBackendError) as ctx:
            self.backend.set("openai", TEST_SECRET_DO_NOT_LEAK)
        self.assertEqual(ctx.exception.provider_id, "openai")
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(ctx.exception))

    def test_set_leaves_no_credential_in_the_backend_frame(self) -> None:
        # INV-6 covers `set` too. The refusal is raised while `credential` is a
        # live local of `set`'s frame, and a frame's locals stay reachable
        # through `exc.__traceback__` after the frame exits, so refusing without
        # scrubbing hands the plaintext to any error reporter that walks frames.
        # Captured with a bare `except`: `assertRaises` clears the frames, which
        # would make this assertion vacuous.
        exc = self._capture(self.backend.set, "openai", TEST_SECRET_DO_NOT_LEAK)

        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIsNotNone(exc.__traceback__)
        by_module = self._frame_locals_by_module(exc)
        # Non-vacuity: the backend's frame really is on this traceback.
        self.assertIn(BACKEND_MODULE, by_module)
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, by_module[BACKEND_MODULE])
        # Called straight from the harness, so the backend frame is the only
        # non-harness frame on this traceback. The graph is therefore clean of
        # any *product-owned* retention -- not clean outright: `_capture` holds
        # the secret in its own `args`, as any caller must, and the module filter
        # excludes it. A test cannot close the originating caller's frame; only
        # the caller can.
        self.assertNotIn(
            TEST_SECRET_DO_NOT_LEAK, self._reachable_exception_payload(exc)
        )

    def test_set_via_store_still_exposes_the_store_frame_known_gap(self) -> None:
        # CHARACTERIZATION TEST -- updated after the base.py INV-6 fix.
        #
        # With the `try/finally: del credential` fix applied to `CredentialStore.set`,
        # the store frame is now also clean. The only frame that can still retain
        # the credential is the originating caller's frame -- outside the credential
        # layer entirely, so no layer-internal change can reach it.
        #
        # This test now verifies the full credential-layer chain is clean: both the
        # backend frame (closed in Phase 5B) and the store frame (closed in the
        # scope-fix pass). The characterization framing is kept because the
        # originating caller's frame remains unobservable from here.
        store = CredentialStore(self.backend)
        exc = self._capture(store.set, "openai", TEST_SECRET_DO_NOT_LEAK)

        self.assertIsInstance(exc, CredentialBackendError)
        by_module = self._frame_locals_by_module(exc)
        # Both credential-layer frames are in scope and both must be clean.
        self.assertIn(BACKEND_MODULE, by_module)
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, by_module[BACKEND_MODULE])
        self.assertIn(BASE_MODULE, by_module)
        self.assertNotIn(
            TEST_SECRET_DO_NOT_LEAK,
            by_module[BASE_MODULE],
            "CredentialStore.set still retains the credential in its frame -- "
            "verify the base.py fix is applied.",
        )

    def test_delete_raises_backend_error(self) -> None:
        with self.assertRaises(CredentialBackendError) as ctx:
            self.backend.delete("openai")
        self.assertEqual(ctx.exception.provider_id, "openai")

    def test_set_does_not_create_a_file(self) -> None:
        try:
            self.backend.set("newprovider", TEST_SECRET_DO_NOT_LEAK)
        except CredentialBackendError:
            pass
        self.assertFalse(
            os.path.exists(os.path.join(self.secrets_dir, "newprovider"))
        )

    def test_delete_does_not_remove_a_file(self) -> None:
        path = self._write_secret("openai", b"value")
        try:
            self.backend.delete("openai")
        except CredentialBackendError:
            pass
        self.assertTrue(os.path.exists(path))


class SecretNonDisclosureTests(_BackendTestBase):
    """INV-6: secret values never appear in repr, str, or exception text."""

    def test_repr_does_not_contain_secret(self) -> None:
        self._write_secret("openai", TEST_SECRET_DO_NOT_LEAK.encode("utf-8"))
        # Even after a successful read, the backend keeps no secret state.
        self.assertEqual(self.backend.get("openai"), TEST_SECRET_DO_NOT_LEAK)
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, repr(self.backend))
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(self.backend))

    def test_provider_credential_masks_secret(self) -> None:
        # Verifies the existing ProviderCredential masking is intact.
        credential = ProviderCredential(api_key=TEST_SECRET_DO_NOT_LEAK)
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, repr(credential))
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, str(credential))
        self.assertEqual(credential.api_key, TEST_SECRET_DO_NOT_LEAK)

    def test_credential_store_repr_masks_secret(self) -> None:
        # Verifies the existing CredentialStore / InMemory masking is intact.
        backend = InMemoryCredentialBackend()
        backend.set("openai", TEST_SECRET_DO_NOT_LEAK)
        store = CredentialStore(backend)
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, repr(store))
        self.assertNotIn(TEST_SECRET_DO_NOT_LEAK, repr(backend))
        self.assertIn("openai", repr(backend))


class SecretsDirValidationTests(_BackendTestBase):
    """An unusable ``secrets_dir`` must fail closed as a credential error.

    ``secrets_dir`` is deployment-supplied and deliberately unvalidated at
    construction time (the mount may appear later), so it first reaches a path
    API on the initial ``get``. Values that no path call can accept would surface
    there as ``TypeError``/``ValueError`` -- types foreign to this seam, which
    bypass the ``CredentialStoreError`` mapping the routing layer depends on.
    """

    def _expect_config_error(self, secrets_dir: object) -> CredentialBackendError:
        backend = ContainerFileCredentialBackend(secrets_dir)  # type: ignore[arg-type]
        exc = self._capture(backend.get, "openai")
        self.assertIsInstance(exc, CredentialBackendError)
        # Stays inside the documented hierarchy, so the routing layer still maps
        # it as a configuration error.
        self.assertIsInstance(exc, CredentialStoreError)
        self.assertNotIsInstance(exc, (TypeError, ValueError))
        assert isinstance(exc, CredentialBackendError)  # narrow for the caller
        return exc

    def test_non_string_secrets_dir_rejected(self) -> None:
        # `os.path.realpath(None)` raises TypeError without this gate.
        exc = self._expect_config_error(None)
        self.assertIn("non-empty string", str(exc))

    def test_bytes_secrets_dir_rejected(self) -> None:
        # `os.path.realpath` accepts bytes and returns bytes; joining that with a
        # str provider_id then raises TypeError deeper in, further from the
        # cause. Rejecting up front keeps the diagnosis at the seam.
        exc = self._expect_config_error(b"/run/secrets")
        self.assertIn("non-empty string", str(exc))

    def test_empty_secrets_dir_rejected(self) -> None:
        # An empty string silently resolves to the process CWD, which would make
        # the containment check pass against an arbitrary directory.
        exc = self._expect_config_error("")
        self.assertIn("non-empty string", str(exc))

    def test_nul_in_secrets_dir_rejected(self) -> None:
        marker = "MARKER_SECRETS_DIR"
        exc = self._expect_config_error(f"/run/{marker}\x00/secrets")
        self.assertIn("NUL", str(exc))
        # The control byte never reaches the message, so it cannot corrupt a log.
        self.assertNotIn("\x00", str(exc))
        # The configured path is not echoed back either: it can carry deployment
        # detail, and the fault is fully described without it.
        self.assertNotIn(marker, str(exc))

    @unittest.skipUnless(
        SURROGATES_UNENCODABLE,
        "platform encodes lone surrogates (Windows surrogatepass)",
    )
    def test_unencodable_secrets_dir_rejected(self) -> None:
        # Without the gate this reaches `os.path.realpath` and surfaces as a bare
        # UnicodeEncodeError.
        exc = self._expect_config_error("/run/secrets\ud800")
        self.assertIn("not encodable", str(exc))

    def test_valid_but_absent_secrets_dir_still_reports_not_found(self) -> None:
        # Guards against over-validation. A directory that does not exist yet is
        # legitimate (the mount is created later), and INV-5 makes a missing
        # secret a normal CredentialNotFoundError, not a configuration failure.
        absent = os.path.join(self.secrets_dir, "not-created-yet")
        backend = ContainerFileCredentialBackend(absent)
        with self.assertRaises(CredentialNotFoundError):
            backend.get("openai")

    def test_secrets_dir_may_contain_separators_and_dotdot(self) -> None:
        # Guards against over-validation: the provider_id rules (no separators,
        # no absolute path, no "..") must NOT be applied to the directory, which
        # legitimately has all three. This path is absolute -- see the relative
        # case below, which is a separate property.
        nested = os.path.join(self.secrets_dir, "sub", "..", "sub")
        self.assertTrue(os.path.isabs(nested))
        os.mkdir(os.path.join(self.secrets_dir, "sub"))
        backend = ContainerFileCredentialBackend(nested)
        path = os.path.join(self.secrets_dir, "sub", "openai")
        with open(path, "wb") as handle:
            handle.write(TEST_SECRET_DO_NOT_LEAK.encode("utf-8"))
        self.assertEqual(backend.get("openai"), TEST_SECRET_DO_NOT_LEAK)

    def test_relative_secrets_dir_is_accepted(self) -> None:
        # A genuinely relative directory: `os.path.join` on a mkdtemp() result
        # yields an absolute path, so the test above does not cover this.
        original = os.getcwd()
        self.addCleanup(os.chdir, original)
        os.chdir(self.secrets_dir)
        os.mkdir("relmount")
        with open(os.path.join("relmount", "openai"), "wb") as handle:
            handle.write(TEST_SECRET_DO_NOT_LEAK.encode("utf-8"))
        backend = ContainerFileCredentialBackend("relmount")
        self.assertFalse(os.path.isabs("relmount"))
        self.assertEqual(backend.get("openai"), TEST_SECRET_DO_NOT_LEAK)

    def test_unavailable_cwd_with_relative_secrets_dir_fails_closed(self) -> None:
        # A relative directory is accepted, which means resolution calls
        # `os.getcwd()` -- and that raises OSError once the working directory has
        # been removed or has lost its execute bit. Validating the *value* cannot
        # see this: every input is well formed, and the failure comes from process
        # state. Without the guard at the resolution site, a bare
        # FileNotFoundError crosses the seam and bypasses the
        # CredentialStoreError mapping the routing layer depends on.
        original = os.getcwd()
        self.addCleanup(os.chdir, original)
        doomed = tempfile.mkdtemp(prefix="cfcb_doomed_")
        os.chdir(doomed)
        try:
            os.rmdir(doomed)
        except OSError as exc:  # pragma: no cover - platform dependent
            os.chdir(original)
            self.skipTest(f"cannot remove the working directory here: {exc}")

        exc = self._capture(
            ContainerFileCredentialBackend("relmount").get, "openai"
        )
        os.chdir(original)

        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIsInstance(exc, CredentialStoreError)
        # The decisive part: no foreign exception type crosses the seam.
        self.assertNotIsInstance(exc, OSError)
        self.assertIn("cannot resolve the secret path", str(exc))

    def test_invalid_provider_id_is_still_reported_first(self) -> None:
        # Ordering matters for C-1: provider_id validation must remain the first
        # stage, so a malformed identifier is refused with no filesystem access
        # at all -- even when the configuration is also broken.
        backend = ContainerFileCredentialBackend(None)  # type: ignore[arg-type]
        # A bare ".." reaches the segment rule; "../escape" would be refused one
        # gate earlier, by the separator check.
        exc = self._capture(backend.get, "..")
        self.assertIsInstance(exc, CredentialBackendError)
        self.assertIn("'..' path segment", str(exc))
        self.assertNotIn("secrets_dir", str(exc))


class ContractAndConfigTests(_BackendTestBase):
    """Type contract and configuration defaults."""

    def test_is_credential_backend_subclass_instance(self) -> None:
        self.assertIsInstance(self.backend, CredentialBackend)

    def test_default_secrets_dir_constant(self) -> None:
        self.assertEqual(DEFAULT_SECRETS_DIR, "/run/secrets")

    def test_default_backend_uses_run_secrets(self) -> None:
        # Construct with the default and confirm via repr WITHOUT reading disk.
        default_backend = ContainerFileCredentialBackend()
        self.assertIn("/run/secrets", repr(default_backend))

    def test_max_size_constant_is_reasonable(self) -> None:
        self.assertIsInstance(MAX_CREDENTIAL_FILE_SIZE_BYTES, int)
        self.assertGreater(MAX_CREDENTIAL_FILE_SIZE_BYTES, 0)


if __name__ == "__main__":
    unittest.main()
