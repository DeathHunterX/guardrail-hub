"""Unit tests for the credential setup adapters.

These cover the thin I/O adapters that back the setup ports:
    - MaskedSecretPrompt provides masked, non-echoed terminal input
    - StreamOutputWriter writes newline-terminated lines and flushes
    - Boto3AwsCredentialDetector fails cleanly (no secret leak) when boto3 is
      unavailable
"""

import io
import sys
import unittest
from unittest import mock

from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.setup.adapters import (
    Boto3AwsCredentialDetector,
    MaskedSecretPrompt,
    SecureInputUnavailableError,
    StreamOutputWriter,
    _read_posix_masked_secret,
    _read_windows_masked_secret,
)


class _TtyInput:
    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        return 37


class _TtyOutput(io.StringIO):
    def isatty(self) -> bool:
        return True


class MaskedSecretPromptTests(unittest.TestCase):
    """The prompt must collect secrets without ever rendering their characters."""

    def test_windows_typing_renders_one_mask_per_character_and_returns_exact_value(self):
        """Dropping a character or echoing it would break masked typing."""
        safe_dummy = "abc123"
        characters = iter([*safe_dummy, "\r"])
        emitted: list[str] = []

        result = _read_windows_masked_secret(
            "Enter API key: ", getwch=lambda: next(characters), putwch=emitted.append,
        )

        self.assertEqual(safe_dummy, result)
        self.assertEqual("Enter API key: " + ("*" * 6) + "\r\n", "".join(emitted))
        self.assertNotIn(safe_dummy, "".join(emitted))

    def test_windows_paste_renders_masks_without_transforming_the_value(self):
        """A paste must be indistinguishable from typing except for speed."""
        safe_dummy = "nvapi-example"
        characters = iter([*safe_dummy, "\r"])
        emitted: list[str] = []

        result = _read_windows_masked_secret(
            "Enter API key: ", getwch=lambda: next(characters), putwch=emitted.append,
        )

        self.assertEqual(safe_dummy, result)
        self.assertEqual("Enter API key: " + ("*" * len(safe_dummy)) + "\r\n", "".join(emitted))
        self.assertNotIn(safe_dummy, "".join(emitted))

    def test_windows_backspace_and_special_keys_keep_mask_and_value_synchronized(self):
        """Navigation-key bytes must not become part of an API key."""
        characters = iter(["a", "b", "c", "\b", "d", "\x00", "K", "\xe0", "M", "\x1b", "\r"])
        emitted: list[str] = []

        result = _read_windows_masked_secret(
            "Enter API key: ", getwch=lambda: next(characters), putwch=emitted.append,
        )

        self.assertEqual("abd", result)
        self.assertEqual("Enter API key: ***\b \b*\r\n", "".join(emitted))

    def test_windows_ctrl_c_and_eof_cancel_without_rendering_input(self):
        """Cancellation must not become a secret or leave the prompt line open."""
        for character, error in (("\003", KeyboardInterrupt), ("\032", EOFError)):
            with self.subTest(character=repr(character)):
                emitted: list[str] = []
                with self.assertRaises(error):
                    _read_windows_masked_secret(
                        "Enter API key: ", getwch=lambda: character, putwch=emitted.append,
                    )
                self.assertEqual("Enter API key: \r\n", "".join(emitted))

    def test_noninteractive_masked_input_fails_closed_with_secret_safe_message(self):
        """Falling back to a visible plain prompt would leak credentials."""
        with mock.patch("app.intelligence.setup.adapters.sys.stdin", io.StringIO()), \
             mock.patch("app.intelligence.setup.adapters.sys.stdout", io.StringIO()):
            with self.assertRaisesRegex(SecureInputUnavailableError, "interactive terminal"):
                MaskedSecretPrompt().read_secret("Enter API key: ")

    def test_posix_restores_terminal_after_enter_and_unexpected_exception(self):
        """Every POSIX exit path must restore the mode captured before cbreak."""
        original = [1, 2, 3]
        terminal_api = mock.Mock(TCSADRAIN=99)
        terminal_api.tcgetattr.return_value = original
        output = _TtyOutput()
        set_cbreak = mock.Mock()

        result = _read_posix_masked_secret(
            "Enter API key: ", input_stream=_TtyInput(), output=output,
            terminal_api=terminal_api, set_cbreak=set_cbreak,
            read_byte=mock.Mock(side_effect=[b"a", b"\r"]),
        )

        self.assertEqual("a", result)
        terminal_api.tcsetattr.assert_called_once_with(37, 99, original)
        self.assertEqual("Enter API key: *\r\n", output.getvalue())

        terminal_api.reset_mock()
        terminal_api.tcgetattr.return_value = original
        with self.assertRaisesRegex(RuntimeError, "boom"):
            _read_posix_masked_secret(
                "Enter API key: ", input_stream=_TtyInput(), output=_TtyOutput(),
                terminal_api=terminal_api, set_cbreak=set_cbreak,
                read_byte=mock.Mock(side_effect=RuntimeError("boom")),
            )
        terminal_api.tcsetattr.assert_called_once_with(37, 99, original)

    def test_posix_restores_terminal_after_cancellation_and_eof(self):
        """Ctrl+C and EOF are terminal exits, so they need the same restoration."""
        original = [1, 2, 3]
        for read_effect, error in ((KeyboardInterrupt(), KeyboardInterrupt), (b"\004", EOFError)):
            with self.subTest(error=error.__name__):
                terminal_api = mock.Mock(TCSADRAIN=99)
                terminal_api.tcgetattr.return_value = original
                read_byte = (
                    mock.Mock(side_effect=read_effect)
                    if isinstance(read_effect, BaseException)
                    else mock.Mock(return_value=read_effect)
                )
                with self.assertRaises(error):
                    _read_posix_masked_secret(
                        "Enter API key: ", input_stream=_TtyInput(), output=_TtyOutput(),
                        terminal_api=terminal_api, set_cbreak=mock.Mock(),
                        read_byte=read_byte,
                    )
                terminal_api.tcsetattr.assert_called_once_with(37, 99, original)

    def test_posix_preserves_utf8_characters_and_masks_backspace_by_character(self):
        """Backspace must remove one decoded character and one mask."""
        original = [1, 2, 3]
        terminal_api = mock.Mock(TCSADRAIN=99)
        terminal_api.tcgetattr.return_value = original
        output = _TtyOutput()

        result = _read_posix_masked_secret(
            "Enter API key: ", input_stream=_TtyInput(), output=output,
            terminal_api=terminal_api, set_cbreak=mock.Mock(),
            read_byte=mock.Mock(side_effect=[b"\xc3", b"\xa9", b"\x7f", b"a", b"\r"]),
        )

        self.assertEqual("a", result)
        self.assertEqual("Enter API key: *\b \b*\r\n", output.getvalue())
        terminal_api.tcsetattr.assert_called_once_with(37, 99, original)

    def test_posix_returns_a_retained_utf8_character_unchanged_with_one_mask(self):
        """Byte-wise decoding would corrupt a retained multibyte credential character."""
        terminal_api = mock.Mock(TCSADRAIN=99)
        terminal_api.tcgetattr.return_value = [1, 2, 3]
        output = _TtyOutput()

        result = _read_posix_masked_secret(
            "Enter API key: ", input_stream=_TtyInput(), output=output,
            terminal_api=terminal_api, set_cbreak=mock.Mock(),
            read_byte=mock.Mock(side_effect=[b"\xc3", b"\xa9", b"\r"]),
        )

        self.assertEqual("é", result)
        self.assertEqual("Enter API key: *\r\n", output.getvalue())

    def test_posix_ignores_delayed_navigation_sequence_bytes(self):
        """A delayed arrow-key suffix must never be accepted as credential text."""
        terminal_api = mock.Mock(TCSADRAIN=99)
        terminal_api.tcgetattr.return_value = [1, 2, 3]
        output = _TtyOutput()

        result = _read_posix_masked_secret(
            "Enter API key: ", input_stream=_TtyInput(), output=output,
            terminal_api=terminal_api, set_cbreak=mock.Mock(),
            read_byte=mock.Mock(side_effect=[b"\x1b", b"[", b"A", b"a", b"\r"]),
        )

        self.assertEqual("a", result)
        self.assertEqual("Enter API key: *\r\n", output.getvalue())


class StreamOutputWriterTests(unittest.TestCase):
    def test_writes_line_with_newline(self):
        buffer = io.StringIO()
        writer = StreamOutputWriter(stream=buffer)

        writer.write_line("hello")
        writer.write_line("world")

        self.assertEqual(buffer.getvalue(), "hello\nworld\n")


class Boto3DetectorTests(unittest.TestCase):
    """When boto3 is unavailable the detector fails cleanly, without leaking."""

    def test_missing_boto3_raises_clean_configuration_error(self):
        detector = Boto3AwsCredentialDetector()

        # Setting the module to None in sys.modules makes `import boto3` raise
        # ImportError deterministically, regardless of whether boto3 is
        # installed in the environment.
        sentinel = object()
        previous = sys.modules.get("boto3", sentinel)
        sys.modules["boto3"] = None  # type: ignore[assignment]
        try:
            with self.assertRaises(LLMConfigurationError) as ctx:
                detector.is_available()
        finally:
            if previous is sentinel:
                del sys.modules["boto3"]
            else:
                sys.modules["boto3"] = previous  # type: ignore[assignment]

        message = str(ctx.exception)
        # A clear, actionable message that names the missing dependency.
        self.assertIn("boto3", message)
        # And it carries no credential-like material.
        self.assertNotIn("secret", message.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
