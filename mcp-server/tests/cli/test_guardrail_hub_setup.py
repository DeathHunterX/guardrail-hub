"""Focused behavioural tests for the approved provider setup state machine."""

from __future__ import annotations

import io
import os
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from app.cli import (
    ProviderStatus,
    _AlternateScreen,
    _ConnectionSpinner,
    _SetupSession,
    _SetupScope,
    _credential_flow,
    _discard_pending_terminal_input,
    _load_validated,
    _main_menu,
    _provider_details_screen,
    _render_external_credential_guidance,
    _resolve_store,
    _select_and_test,
    _test_flow,
    main,
)
from app.intelligence.credentials import CredentialBackendError, CredentialNotFoundError, CredentialStore, InMemoryCredentialBackend
from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.setup.connection import ConnectionResult, ConnectionState


_CONFIG = """\
llm:
  providers:
    - id: local
      type: ollama
      deployment: self_hosted
      enabled: true
      auth: {type: none}
      connection: {base_url: http://localhost:11434}
      models:
        - id: local-chat
          type: chat
          capabilities: [chat]
    - id: cloud
      type: openai_compatible
      deployment: cloud
      enabled: true
      auth: {type: api_key, api_key_env: CLOUD_KEY}
      connection: {base_url: https://example.invalid/v1}
      models:
        - id: cloud-chat
          type: chat
          capabilities: [chat]
    - id: disabled
      type: openai_compatible
      deployment: cloud
      enabled: false
      auth: {type: api_key, api_key_env: DISABLED_KEY}
      connection: {base_url: https://example.invalid/v1}
      models: []
"""

_AWS_PROVIDER = """\
    - id: bedrock
      type: bedrock
      deployment: cloud
      enabled: true
      auth: {type: aws}
      connection: {region: us-east-1}
      models: []
"""


class _Output:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.fragments: list[str] = []
        self.flush_count = 0

    def write_line(self, text: str) -> None:
        self.lines.append(text)

    def write(self, text: str) -> None:
        self.fragments.append(text)

    def flush(self) -> None:
        self.flush_count += 1

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class _Prompt:
    def __init__(self, *values: str) -> None:
        self.values = list(values)
        self.calls = 0
        self.labels: list[str] = []

    def read_secret(self, label: str) -> str:
        self.calls += 1
        self.labels.append(label)
        return self.values.pop(0)


class _Tester:
    def __init__(self, *results: ConnectionResult) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, str | None]] = []

    def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
        self.calls.append((provider.provider_id, candidate_credential))
        return self.results.pop(0)


class _AwsDetector:
    def __init__(self, available: bool = False) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


class _TtyStream(io.StringIO):
    def isatty(self) -> bool:
        return True


class _WindowsTtyStream(_TtyStream):
    def fileno(self) -> int:
        return 42


def _windows_console_modules(
    events: list[tuple], *, original_mode: int = 0x0003, set_succeeds: bool = True,
):
    import ctypes

    class Kernel32:
        @staticmethod
        def GetConsoleMode(handle, mode) -> int:
            events.append(("get", handle))
            mode._obj.value = original_mode
            return 1

        @staticmethod
        def SetConsoleMode(handle, mode) -> int:
            events.append(("set", handle, mode))
            return int(set_succeeds)

    fake_ctypes = types.SimpleNamespace(
        byref=ctypes.byref,
        c_uint=ctypes.c_uint,
        windll=types.SimpleNamespace(kernel32=Kernel32()),
    )
    fake_msvcrt = types.SimpleNamespace(get_osfhandle=lambda descriptor: descriptor + 100)
    return {"ctypes": fake_ctypes, "msvcrt": fake_msvcrt}


class _TerminalOutput:
    """Route setup presentation through the same pseudo-terminal as ANSI output."""

    def __init__(self, terminal: io.StringIO) -> None:
        self._terminal = terminal

    def write_line(self, text: str) -> None:
        self._terminal.write(text + "\n")

    def write(self, text: str) -> None:
        self._terminal.write(text)

    def flush(self) -> None:
        self._terminal.flush()


class AlternateScreenTests(unittest.TestCase):
    def test_windows_tty_without_term_uses_actual_console_capability(self) -> None:
        terminal = _TtyStream()
        restore_events: list[str] = []

        with mock.patch("app.cli.os.name", "nt"), \
             mock.patch(
                 "app.cli._enable_windows_vt",
                 create=True,
                 return_value=(True, lambda: restore_events.append("restore")),
             ):
            with _AlternateScreen(terminal, _TtyStream(), term=None):
                pass

        self.assertEqual(1, terminal.getvalue().count("\x1b[?1049h"))
        self.assertEqual(1, terminal.getvalue().count("\x1b[?1049l"))
        self.assertEqual(["restore"], restore_events)

    def test_windows_tty_with_misleading_dumb_term_uses_actual_console_capability(self) -> None:
        terminal = _TtyStream()

        with mock.patch("app.cli.os.name", "nt"), \
             mock.patch(
                 "app.cli._enable_windows_vt",
                 create=True,
                 return_value=(True, lambda: None),
             ):
            with _AlternateScreen(terminal, _TtyStream(), term="dumb"):
                pass

        self.assertIn("\x1b[?1049h", terminal.getvalue())
        self.assertIn("\x1b[?1049l", terminal.getvalue())

    def test_posix_tty_without_term_uses_screen_replacement(self) -> None:
        terminal = _TtyStream()

        with mock.patch("app.cli.os.name", "posix"), \
             mock.patch.dict(os.environ, {}, clear=True):
            with _AlternateScreen(terminal, _TtyStream(), term=None):
                pass

        self.assertEqual(
            "\x1b[?1049h\x1b[H\x1b[?25h\x1b[?25h\x1b[?1049l",
            terminal.getvalue(),
        )

    def test_posix_tty_with_dumb_term_uses_inline_fallback(self) -> None:
        terminal = _TtyStream()

        with mock.patch("app.cli.os.name", "posix"):
            with _AlternateScreen(terminal, _TtyStream(), term="dumb"):
                pass

        self.assertEqual("", terminal.getvalue())

    def test_one_session_enters_and_leaves_once_across_multiple_transitions(self) -> None:
        terminal = _TtyStream()

        with mock.patch("app.cli.os.name", "posix"):
            with _AlternateScreen(terminal, _TtyStream(), term="xterm-256color") as screen:
                screen.redraw()
                screen.redraw()
                screen.redraw()

        rendered = terminal.getvalue()
        self.assertEqual(1, rendered.count("\x1b[?1049h"))
        self.assertEqual(3, rendered.count("\x1b[2J\x1b[H"))
        self.assertEqual(1, rendered.count("\x1b[?1049l"))

    def test_windows_vt_mode_is_enabled_and_exactly_restored_after_exceptions(self) -> None:
        for exception_type in (KeyboardInterrupt, EOFError, RuntimeError):
            with self.subTest(exception_type=exception_type.__name__):
                terminal = _WindowsTtyStream()
                events: list[tuple] = []
                modules = _windows_console_modules(events)

                with mock.patch("app.cli.os.name", "nt"), \
                     mock.patch.dict("sys.modules", modules):
                    with self.assertRaises(exception_type):
                        with _AlternateScreen(terminal, _TtyStream(), term=None):
                            raise exception_type("stop")

                self.assertEqual(
                    [("get", 142), ("set", 142, 0x0007), ("set", 142, 0x0003)],
                    events,
                )
                self.assertEqual(1, terminal.getvalue().count("\x1b[?1049h"))
                self.assertEqual(1, terminal.getvalue().count("\x1b[?1049l"))

    def test_native_windows_console_does_not_use_ansi_when_vt_enablement_fails(self) -> None:
        terminal = _WindowsTtyStream()
        events: list[tuple] = []
        modules = _windows_console_modules(events, set_succeeds=False)

        with mock.patch("app.cli.os.name", "nt"), \
             mock.patch.dict("sys.modules", modules):
            with _AlternateScreen(terminal, _TtyStream(), term="xterm-256color"):
                pass

        self.assertEqual([("get", 142), ("set", 142, 0x0007)], events)
        self.assertEqual("", terminal.getvalue())

    def test_alternate_screen_restores_terminal_after_an_error(self) -> None:
        """A thrown setup error must leave the operator's original screen usable."""
        output = _TtyStream()
        screen = _AlternateScreen(output, _TtyStream(), term="xterm-256color")

        with self.assertRaises(RuntimeError):
            with screen:
                raise RuntimeError("boom")

        self.assertEqual("\x1b[?1049h\x1b[H\x1b[?25h\x1b[?25h\x1b[?1049l", output.getvalue())

    def test_alternate_screen_falls_back_when_stdout_is_not_a_tty(self) -> None:
        output = io.StringIO()
        with _AlternateScreen(output, _TtyStream(), term="xterm-256color"):
            pass
        self.assertEqual("", output.getvalue())

    def test_redraw_clears_and_homes_only_while_alternate_mode_is_active(self) -> None:
        terminal = _TtyStream()
        screen = _AlternateScreen(terminal, _TtyStream(), term="xterm-256color")
        screen.redraw()
        with screen:
            screen.redraw()
        self.assertEqual(
            "\x1b[?1049h\x1b[H\x1b[?25h\x1b[2J\x1b[H\x1b[?25h\x1b[?1049l",
            terminal.getvalue(),
        )

    def test_help_and_parser_errors_never_construct_an_alternate_screen(self) -> None:
        with mock.patch("app.cli._AlternateScreen") as screen:
            with self.assertRaises(SystemExit):
                main(["setup", "--help"])
            with self.assertRaises(SystemExit):
                main(["setup", "--credential"])
        screen.assert_not_called()


class SetupStateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Path(self.directory.name) / "llm.yaml"
        self.config.write_text(_CONFIG, encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"REGISTRY_LLM_CONFIG_PATH": str(self.config)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def _store(self) -> CredentialStore:
        return CredentialStore(InMemoryCredentialBackend())

    def _configured_store(self, provider_id: str) -> CredentialStore:
        store = self._store()
        store.set(provider_id, "configured-only-for-test")
        return store

    @staticmethod
    def _choose_last(label: str) -> str:
        return label.rpartition("-")[2].split("]", maxsplit=1)[0]

    def test_dashboard_uses_the_approved_structured_setup_presentation(self) -> None:
        output = _Output()
        prompts: list[str] = []
        code = main(
            ["setup"], credential_store=self._store(), output=output,
            input_reader=lambda prompt: prompts.append(prompt) or "4",
        )
        self.assertEqual(0, code)
        self.assertIn("Guardrail Hub — LLM Setup", output.text)
        self.assertIn("Providers", output.text)
        self.assertIn("✗ cloud", output.text)
        self.assertIn("Authentication: API Key", output.text)
        self.assertIn("Status: Missing credential", output.text)
        self.assertIn("Summary", output.text)
        self.assertIn("Ready:", output.text)
        self.assertIn("Missing:", output.text)
        self.assertIn("Total:", output.text)
        self.assertIn("What would you like to do?", output.text)
        self.assertEqual(["Select [1-4]: "], prompts)

    def test_no_change_exit_renders_only_initial_dashboard(self) -> None:
        output = _Output()
        main(["setup"], credential_store=self._store(), output=output, input_reader=lambda _prompt: "4")
        self.assertEqual(1, output.text.count("Ready:"))

    def test_interactive_navigation_redraws_between_screens(self) -> None:
        """A real screen transition clears the alternate screen before rendering it."""
        terminal = _TtyStream()
        answers = iter(["3", "2", "2", "4", "4"])
        with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}), \
             mock.patch("app.cli.sys.stdout", terminal), \
             mock.patch("app.cli.sys.stdin", _TtyStream()):
            code = main(
                ["setup"], credential_store=self._store(),
                output=_TerminalOutput(terminal), input_reader=lambda _prompt: next(answers),
            )

        self.assertEqual(0, code)
        rendered = terminal.getvalue()
        self.assertIn("\x1b[?1049h", rendered)
        self.assertGreaterEqual(rendered.count("\x1b[2J\x1b[H"), 3)
        self.assertIn("Provider Details", rendered)
        self.assertIn("\x1b[?25h\x1b[?1049l", rendered)

    def test_plain_output_navigation_emits_no_terminal_control_sequences(self) -> None:
        output = _Output()
        answers = iter(["3", "2", "2", "4", "4"])
        self.assertEqual(
            0,
            main(["setup"], credential_store=self._store(), output=output,
                 input_reader=lambda _prompt: next(answers)),
        )
        self.assertNotIn("\x1b[", output.text)

    def test_invalid_dashboard_input_does_not_redraw_or_rescan(self) -> None:
        """Validation feedback remains inline on the current dashboard screen."""
        result, _ = _load_validated(self.config)
        statuses = {
            item.provider_id: ProviderStatus(item, "missing" if item.provider_id == "cloud" else "not_required")
            for item in result.providers if item.enabled
        }
        output = _Output()
        redraws: list[str] = []
        answers = iter(["wrong", "9", "4"])
        _main_menu(
            _SetupSession(statuses, redraw=lambda: redraws.append("redraw")),
            self._store(), None, _Prompt(), output, lambda _prompt: next(answers), False,
        )
        self.assertEqual([], redraws)
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1, 2, 3, or 4."))

    def test_nested_back_returns_to_dashboard_and_keeps_exit_there(self) -> None:
        output = _Output()
        answers = iter(["3", "2", "2", "4", "4"])
        self.assertEqual(
            0,
            main(["setup"], credential_store=self._store(), output=output,
                 input_reader=lambda _prompt: next(answers)),
        )
        self.assertIn("Back to provider details selection", output.text)
        self.assertGreaterEqual(output.text.count("Guardrail Hub — LLM Setup"), 2)

    def test_provider_shortcut_uses_the_details_screen_navigation(self) -> None:
        output = _Output()
        self.assertEqual(
            0,
            main(["setup", "--provider", "cloud"], credential_store=self._store(), output=output,
                 input_reader=lambda _prompt: "2"),
        )
        self.assertIn("Provider Details", output.text)
        self.assertIn("2. Exit", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_provider_scoped_details_exit_without_rendering_dashboard(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()
        store = self._configured_store("nvidia-nim")

        code = main(
            ["setup", "--provider", "nvidia-nim"],
            credential_store=store,
            output=output,
            input_reader=lambda _prompt, answers=iter(["3"]): next(answers),
        )

        self.assertEqual(0, code)
        self.assertIn("Provider Details", output.text)
        self.assertIn("3. Exit", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_provider_scoped_test_retries_and_returns_to_same_provider(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()
        store = self._configured_store("nvidia-nim")
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )

        code = main(
            ["setup", "--provider", "nvidia-nim"],
            credential_store=store,
            connection_tester=tester,
            output=output,
            input_reader=lambda _prompt, answers=iter(["2", "1", "2", "3"]): next(answers),
        )

        self.assertEqual(0, code)
        self.assertEqual(
            [("nvidia-nim", "configured-only-for-test")] * 2,
            tester.calls,
        )
        self.assertEqual(2, output.text.count("Provider Details"))
        self.assertIn("Back to provider", output.text)
        self.assertNotIn("Test another provider", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_provider_scoped_configure_returns_to_refreshed_details(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()
        store = self._store()

        code = main(
            ["setup", "--provider", "nvidia-nim", "--credential"],
            credential_store=store,
            secret_prompt=_Prompt("candidate-only-secret"),
            connection_tester=_Tester(ConnectionResult(ConnectionState.READY, "Connection successful")),
            output=output,
            input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
        )

        self.assertEqual(0, code)
        self.assertEqual("candidate-only-secret", store.get("nvidia-nim"))
        details = output.text.rsplit("Provider Details", maxsplit=1)[1]
        self.assertIn("Credential: Configured", details)
        self.assertNotIn("Configure another missing provider", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_provider_scoped_failed_configure_backs_to_same_provider(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()

        code = main(
            ["setup", "--provider", "nvidia-nim"],
            credential_store=self._store(),
            secret_prompt=_Prompt("candidate-only-secret"),
            connection_tester=_Tester(ConnectionResult(ConnectionState.FAILED, "Connection failed")),
            output=output,
            input_reader=lambda _prompt, answers=iter(["1", "3", "2"]): next(answers),
        )

        self.assertEqual(0, code)
        self.assertIn("Credential: Missing", output.text.rsplit("Provider Details", maxsplit=1)[1])
        self.assertNotIn("Configure another missing provider", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_provider_scoped_reconfigure_retries_candidate_then_refreshes_details(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()
        store = self._configured_store("nvidia-nim")
        tester = _Tester(
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )

        code = main(
            ["setup", "--provider", "nvidia-nim"],
            credential_store=store,
            secret_prompt=_Prompt("failed-candidate", "replacement-candidate"),
            connection_tester=tester,
            output=output,
            input_reader=lambda _prompt, answers=iter(["1", "1", "2", "3"]): next(answers),
        )

        self.assertEqual(0, code)
        self.assertEqual("replacement-candidate", store.get("nvidia-nim"))
        self.assertEqual(
            [("nvidia-nim", "failed-candidate"), ("nvidia-nim", "replacement-candidate")],
            tester.calls,
        )
        self.assertIn("Credential: Configured", output.text.rsplit("Provider Details", maxsplit=1)[1])
        self.assertNotIn("Reconfigure another provider", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_provider_scoped_read_only_details_offer_only_exit(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()
        prompt = _Prompt("must-not-be-read")

        with mock.patch("app.cli._resolve_store", return_value=(self._store(), True, False)):
            code = main(
                ["setup", "--provider", "nvidia-nim"],
                secret_prompt=prompt,
                output=output,
                input_reader=lambda _prompt: "1",
            )

        self.assertEqual(0, code)
        self.assertEqual(0, prompt.calls)
        self.assertIn("read-only runtime context", output.text)
        self.assertIn("Provider Details", output.text)
        self.assertIn("1. Exit", output.text.rsplit("Provider Details", maxsplit=1)[1])
        self.assertNotIn("Configure credential", output.text)
        self.assertNotIn("Reconfigure credential", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_test_result_supports_retry_switch_target_and_dashboard_back(self) -> None:
        """Test result navigation stays in its screen hierarchy instead of appending menus."""
        output = _Output()
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )
        answers = iter(["2", "1", "1", "2", "2", "4"])
        self.assertEqual(
            0,
            main(["setup"], credential_store=self._store(), connection_tester=tester, output=output,
                 input_reader=lambda _prompt: next(answers)),
        )
        self.assertEqual([("local", None), ("local", None)], tester.calls)
        self.assertGreaterEqual(output.text.count("Guardrail Hub — Test Connection"), 3)
        self.assertIn("Test another provider", output.text)
        self.assertIn("Back to main menu", output.text)

    def test_provider_test_flow_stays_in_test_context_for_again_and_another(self) -> None:
        """Connection results offer a direct retry or target switch without a dashboard round trip."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store, output = self._store(), _Output()
        store.set("cloud", "stored-test-only-credential")
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )
        session = _SetupSession({
            "local": ProviderStatus(local, "not_required"),
            "cloud": ProviderStatus(cloud, "configured"),
        })
        answers = iter(["1", "1", "2", "2", "3"])
        _select_and_test(
            [local, cloud], session, store, tester, output, lambda _prompt: next(answers),
        )
        self.assertIn("Guardrail Hub — Test Connection", output.text)
        self.assertIn("Providers available for connection testing", output.text)
        self.assertIn("1. Test again", output.text)
        self.assertIn("2. Test another provider", output.text)
        self.assertIn("3. Back to main menu", output.text)
        self.assertNotIn("Exit", output.text)
        self.assertEqual(
            [("local", None), ("local", None), ("cloud", "stored-test-only-credential")],
            tester.calls,
        )
        self.assertFalse(session.changed)

    def test_provider_details_test_connection_uses_the_shared_test_result_actions(self) -> None:
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        output = _Output()
        outcome = _provider_details_screen(
            local, _SetupSession({"local": ProviderStatus(local, "not_required")}), self._store(),
            _Tester(ConnectionResult(ConnectionState.FAILED, "Connection failed")), _Prompt(), output,
            lambda _prompt, answers=iter(["1", "3"]): next(answers), False, parent="dashboard",
        )
        self.assertEqual("dashboard", outcome)
        self.assertIn("Guardrail Hub — Test Connection", output.text)
        self.assertIn("Test again", output.text)
        self.assertIn("Test another provider", output.text)
        self.assertIn("Back to main menu", output.text)
        self.assertNotIn("Exit", output.text)

    def test_test_selection_uses_only_currently_testable_provider_states(self) -> None:
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        disabled = next(item for item in result.providers if item.provider_id == "disabled")
        output = _Output()
        answers = iter(["1", "3", "3"])
        _main_menu(
            _SetupSession({
                "local": ProviderStatus(local, "not_required"),
                "cloud": ProviderStatus(cloud, "externally_managed"),
                "disabled": ProviderStatus(disabled, "configured"),
            }),
            self._store(), None, _Prompt(), output, lambda _prompt: next(answers), True,
        )
        selection = output.text.split("Providers available for connection testing", 1)[1].split(
            "Guardrail Hub — LLM Setup", 1,
        )[0]
        self.assertIn("1. local", selection)
        self.assertIn("2. cloud", selection)
        self.assertNotIn("disabled", selection)

    def test_provider_shortcut_test_connection_enters_shared_test_result(self) -> None:
        output = _Output()
        self.assertEqual(
            0,
            main(
                ["setup", "--provider", "local"], credential_store=self._store(),
                connection_tester=_Tester(ConnectionResult(ConnectionState.FAILED, "Connection failed")),
                output=output, input_reader=lambda _prompt, answers=iter(["1", "3"]): next(answers),
            ),
        )
        self.assertIn("Guardrail Hub — Test Connection", output.text)
        self.assertIn("Back to provider", output.text)
        self.assertNotIn("Test another provider", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_missing_credential_failure_retests_transient_candidate_then_persists_only_success(self) -> None:
        store, output = self._store(), _Output()
        first, second = "first-candidate", "second-candidate"
        tester = _Tester(
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )
        self.assertEqual(
            0,
            main(
                ["setup", "--provider", "cloud", "--credential"], credential_store=store,
                secret_prompt=_Prompt(first, second), connection_tester=tester, output=output,
                input_reader=lambda _prompt, answers=iter(["2", "1", "2", "3"]): next(answers),
            ),
        )
        self.assertEqual(
            [("cloud", first), ("cloud", first), ("cloud", second)], tester.calls,
        )
        self.assertEqual(second, store.get("cloud"))
        self.assertNotIn(first, output.text)
        self.assertNotIn(second, output.text)
        self.assertIn("Guardrail Hub — Configure Credential", output.text)
        self.assertIn("Credential was not stored.", output.text)
        self.assertIn("Enter another API key", output.text)
        self.assertIn("Test again", output.text)
        self.assertIn("Back to provider", output.text)
        self.assertIn("Exit", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_reconfigure_failure_retests_candidate_and_preserves_old_credential(self) -> None:
        store, output = self._store(), _Output()
        store.set("cloud", "old-valid-secret")
        replacement = "replacement-candidate"
        tester = _Tester(
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
        )
        self.assertEqual(
            0,
            main(
                ["setup", "--provider", "cloud", "--reconfigure"], credential_store=store,
                secret_prompt=_Prompt(replacement), connection_tester=tester, output=output,
                input_reader=lambda _prompt, answers=iter(["2", "3", "3"]): next(answers),
            ),
        )
        self.assertEqual([("cloud", replacement), ("cloud", replacement)], tester.calls)
        self.assertEqual("old-valid-secret", store.get("cloud"))
        self.assertNotIn(replacement, output.text)
        self.assertIn("Guardrail Hub — Reconfigure Credential", output.text)
        self.assertIn("Existing credential was not changed.", output.text)

    def test_missing_credential_selection_uses_writable_missing_api_key_providers_only(self) -> None:
        output = _Output()
        self.assertEqual(
            0,
            main(
                ["setup"], credential_store=self._store(), output=output,
                input_reader=lambda _prompt, answers=iter(["1", "2", "4"]): next(answers),
            ),
        )
        self.assertIn("Guardrail Hub — Configure Credential", output.text)
        self.assertIn("Providers missing credentials", output.text)
        self.assertIn("1. cloud", output.text)
        self.assertNotIn("disabled\n2. Back", output.text)

    def test_missing_credential_success_switches_directly_to_remaining_missing_provider(self) -> None:
        second = """    - id: cloud-two
      type: openai_compatible
      deployment: cloud
      enabled: true
      auth: {type: api_key, api_key_env: CLOUD_TWO_KEY}
      connection: {base_url: https://example.invalid/v1}
      models: []
"""
        self.config.write_text(_CONFIG.replace("    - id: disabled", second + "    - id: disabled"), encoding="utf-8")
        store, output = self._store(), _Output()
        self.assertEqual(
            0,
            main(
                ["setup"], credential_store=store,
                secret_prompt=_Prompt("first-safe-candidate", "second-safe-candidate"),
                connection_tester=_Tester(
                    ConnectionResult(ConnectionState.READY, "Connection successful"),
                    ConnectionResult(ConnectionState.READY, "Connection successful"),
                ),
                output=output, input_reader=lambda _prompt, answers=iter(["1", "1", "2", "1", "2", "4"]): next(answers),
            ),
        )
        self.assertEqual("first-safe-candidate", store.get("cloud"))
        self.assertEqual("second-safe-candidate", store.get("cloud-two"))
        self.assertIn("Configure another missing provider", output.text)
        self.assertGreaterEqual(output.text.count("Providers missing credentials"), 2)

    def test_missing_credential_success_test_again_uses_persisted_credential_without_reprompt(self) -> None:
        store, output = self._store(), _Output()
        candidate = "candidate-only-secret"
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )
        self.assertEqual(
            0,
            main(
                ["setup", "--provider", "cloud", "--credential"], credential_store=store,
                secret_prompt=_Prompt(candidate), connection_tester=tester, output=output,
                input_reader=lambda _prompt, answers=iter(["1", "2", "3"]): next(answers),
            ),
        )
        self.assertEqual([("cloud", candidate), ("cloud", candidate)], tester.calls)
        self.assertEqual(candidate, store.get("cloud"))
        self.assertNotIn("Configure another missing provider", output.text)

    def test_reconfigure_success_test_again_uses_replaced_credential_after_validation(self) -> None:
        store, output = self._store(), _Output()
        store.set("cloud", "old-valid-secret")
        replacement = "replacement-only-secret"
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )
        self.assertEqual(
            0,
            main(
                ["setup", "--provider", "cloud", "--reconfigure"], credential_store=store,
                secret_prompt=_Prompt(replacement), connection_tester=tester, output=output,
                input_reader=lambda _prompt, answers=iter(["1", "2", "3"]): next(answers),
            ),
        )
        self.assertEqual([("cloud", replacement), ("cloud", replacement)], tester.calls)
        self.assertEqual(replacement, store.get("cloud"))
        self.assertIn("Credential updated securely", output.text)

    def test_reconfigure_selection_lists_only_configured_writable_providers(self) -> None:
        store, output = self._store(), _Output()
        store.set("cloud", "old-valid-secret")
        self.assertEqual(
            0,
            main(
                ["setup"], credential_store=store, output=output,
                input_reader=lambda _prompt, answers=iter(["1", "2", "4"]): next(answers),
            ),
        )
        self.assertIn("Guardrail Hub — Reconfigure Credential", output.text)
        self.assertIn("Configured providers", output.text)
        self.assertIn("1. cloud", output.text)
        self.assertNotIn("disabled\n2. Back", output.text)

    def test_read_only_credential_shortcut_uses_credential_required_screen(self) -> None:
        output = _Output()
        with mock.patch("app.cli._resolve_store", return_value=(self._store(), True, False)):
            self.assertEqual(
                0,
                main(
                    ["setup", "--provider", "cloud", "--credential"], output=output,
                    input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
                ),
            )
        self.assertIn("Guardrail Hub — Credential Required", output.text)
        self.assertIn("Credential changes are unavailable inside the running MCP container.", output.text)
        self.assertNotIn("Enter API key", output.text)

    def test_read_only_reconfigure_shortcut_preserves_configured_provider_state(self) -> None:
        store, output = self._store(), _Output()
        store.set("cloud", "stored-test-only-credential")
        with mock.patch("app.cli._resolve_store", return_value=(store, True, False)):
            self.assertEqual(
                0,
                main(
                    ["setup", "--provider", "cloud", "--reconfigure"], output=output,
                    input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
                ),
            )
        self.assertIn("Credential: Configured", output.text)
        self.assertNotIn("Enter new API key", output.text)

    def test_blank_credential_input_retries_inline_before_persisting(self) -> None:
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store, output, redraws = self._store(), _Output(), []
        prompt = _Prompt("", "candidate-only-secret")
        session = _SetupSession({"cloud": ProviderStatus(cloud, "missing")}, redraw=lambda: redraws.append("redraw"))
        self.assertEqual(
            "dashboard",
            _credential_flow(
                cloud, False, [cloud], session, store,
                _Tester(ConnectionResult(ConnectionState.READY, "Connection successful")),
                prompt, output, lambda _prompt: "2",
            ),
        )
        self.assertEqual(2, prompt.calls)
        self.assertEqual(["redraw"], redraws)
        self.assertIn("No credential entered. Please try again.", output.text)
        self.assertEqual("candidate-only-secret", store.get("cloud"))

    def test_secure_input_feedback_follows_valid_entry_and_forwards_candidate_unchanged(self) -> None:
        """Removing acknowledgement or mutating secure input must fail before a probe starts."""
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store, output = self._store(), _Output()
        safe_dummy = " safe-pasted-dummy "

        class ReadyTester:
            def test(_self, _provider, *, candidate_credential=None) -> ConnectionResult:
                self.assertEqual(safe_dummy, candidate_credential)
                self.assertIn("Credential received. Testing connection...", output.text)
                self.assertNotIn(safe_dummy, output.text)
                with self.assertRaises(CredentialNotFoundError):
                    store.get("cloud")
                return ConnectionResult(ConnectionState.READY, "Connection successful")

        outcome = _credential_flow(
            cloud, False, [cloud], _SetupSession({"cloud": ProviderStatus(cloud, "missing")}), store,
            ReadyTester(), _Prompt("", safe_dummy), output,
            lambda _prompt: "2",
        )

        self.assertEqual("dashboard", outcome)
        self.assertIn("No credential entered. Please try again.", output.text)
        self.assertEqual(1, output.text.count("Credential received. Testing connection..."))
        self.assertEqual(safe_dummy, store.get("cloud"))
        self.assertNotIn(safe_dummy, output.text)

    def test_failed_probe_after_secure_input_never_persists_candidate(self) -> None:
        """A failed probe must keep the captured candidate out of the credential store."""
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store, output = self._store(), _Output()
        safe_dummy = "typed-safe-dummy"

        class FailedTester:
            def test(_self, _provider, *, candidate_credential=None) -> ConnectionResult:
                self.assertEqual(safe_dummy, candidate_credential)
                self.assertIn("Credential received. Testing connection...", output.text)
                with self.assertRaises(CredentialNotFoundError):
                    store.get("cloud")
                return ConnectionResult(ConnectionState.FAILED, "Connection failed")

        outcome = _credential_flow(
            cloud, False, [cloud], _SetupSession({"cloud": ProviderStatus(cloud, "missing")}), store,
            FailedTester(), _Prompt(safe_dummy), output,
            lambda _prompt: "3",
        )

        self.assertEqual("dashboard", outcome)
        self.assertIn("Credential was not stored.", output.text)
        with self.assertRaises(CredentialNotFoundError):
            store.get("cloud")
        self.assertNotIn(safe_dummy, output.text)

    def test_interactive_provider_test_transitions_redraw_selection_result_and_dashboard(self) -> None:
        terminal = _TtyStream()
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
        )
        answers = iter(["2", "1", "1", "2", "2", "4"])
        with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}), \
             mock.patch("app.cli.sys.stdout", terminal), \
             mock.patch("app.cli.sys.stdin", _TtyStream()):
            self.assertEqual(
                0,
                main(
                    ["setup"], credential_store=self._store(), connection_tester=tester,
                    output=_TerminalOutput(terminal), input_reader=lambda _prompt: next(answers),
                ),
            )
        rendered = terminal.getvalue()
        self.assertGreaterEqual(rendered.count("\x1b[2J\x1b[H"), 5)
        self.assertEqual(2, tester.calls.count(("local", None)))
        self.assertGreaterEqual(rendered.count("Guardrail Hub — Test Connection"), 3)

    def test_interactive_provider_test_switch_selects_a_second_provider_without_dashboard(self) -> None:
        terminal = _TtyStream()
        store = self._store()
        store.set("cloud", "stored-test-only-credential")
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
        )
        answers = iter(["2", "1", "2", "2", "3", "4"])
        with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}), \
             mock.patch("app.cli.sys.stdout", terminal), \
             mock.patch("app.cli.sys.stdin", _TtyStream()):
            self.assertEqual(
                0,
                main(
                    ["setup"], credential_store=store, connection_tester=tester,
                    output=_TerminalOutput(terminal), input_reader=lambda _prompt: next(answers),
                ),
            )
        rendered = terminal.getvalue()
        self.assertEqual([("local", None), ("cloud", "stored-test-only-credential")], tester.calls)
        self.assertGreaterEqual(rendered.count("\x1b[2J\x1b[H"), 5)

    def test_reconfigure_shortcut_uses_the_shared_entry_and_result_screens(self) -> None:
        store, output = self._store(), _Output()
        store.set("cloud", "old-valid-secret")
        self.assertEqual(
            0,
            main(
                ["setup", "--provider", "cloud", "--reconfigure"], credential_store=store,
                secret_prompt=_Prompt("replacement-secret"),
                connection_tester=_Tester(ConnectionResult(ConnectionState.READY, "Connection successful")),
                output=output, input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
            ),
        )
        self.assertIn("Guardrail Hub — Reconfigure Credential", output.text)
        self.assertIn("Credential updated securely", output.text)
        self.assertEqual("replacement-secret", store.get("cloud"))
        self.assertIn("Provider Details", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_invalid_test_result_input_stays_inline_without_retesting(self) -> None:
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        output, redraws = _Output(), []
        tester = _Tester(ConnectionResult(ConnectionState.READY, "Connection successful"))
        answers = iter(["bad", "9", "3"])
        outcome = _test_flow(
            local, [local], _SetupSession({"local": ProviderStatus(local, "not_required")}, redraw=lambda: redraws.append("redraw")),
            self._store(), tester, output, lambda _prompt: next(answers),
        )
        self.assertEqual("dashboard", outcome)
        self.assertEqual([("local", None)], tester.calls)
        self.assertEqual(["redraw"], redraws)
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1, 2, or 3."))

    def test_provider_test_waiting_screen_precedes_probe_and_retries_before_each_probe(self) -> None:
        """A delayed connection probe must never leave the previous screen visible."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        events: list[str] = []

        class EventOutput(_Output):
            def write_line(self, text: str) -> None:
                super().write_line(text)
                if text == "✓ Connection successful":
                    events.append("render_result")

            def write(self, text: str) -> None:
                super().write(text)
                if text.startswith("\r") and "Testing connection..." in text:
                    events.append("render_waiting")

        class DelayedTester:
            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                events.append("probe")
                return ConnectionResult(ConnectionState.READY, "Connection successful")

        output, redraws = EventOutput(), []
        session = _SetupSession(
            {"local": ProviderStatus(local, "not_required")},
            scope=_SetupScope.provider("local"),
            redraw=lambda: redraws.append("redraw"),
        )
        outcome = _test_flow(
            local,
            [local],
            session,
            self._store(),
            DelayedTester(),
            output,
            lambda _prompt, answers=iter(["1", "3"]): next(answers),
        )

        self.assertEqual("exit", outcome)
        self.assertEqual(
            [
                "render_waiting", "probe", "render_result",
                "render_waiting", "probe", "render_result",
            ],
            events,
        )
        self.assertEqual(2, sum("Testing connection..." in fragment for fragment in output.fragments))
        self.assertEqual(2, output.text.count("✓ Connection successful"))
        self.assertEqual(["redraw", "redraw", "redraw"], redraws)
        self.assertIn("2. Back to provider", output.text)
        self.assertIn("3. Exit", output.text)
        self.assertNotIn("Test another provider", output.text)
        self.assertNotIn("Back to main menu", output.text)

    def test_connection_spinner_flushes_header_and_first_frame_before_a_blocked_probe(self) -> None:
        """A probe starts only after an explicitly flushed, live waiting state."""
        import queue

        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        frames: queue.Queue[str] = queue.Queue()
        events: list[str] = []
        release_probe = threading.Event()
        case = self

        class RecordingOutput(_Output):
            def write_line(self, text: str) -> None:
                super().write_line(text)
                events.append(f"line:{text}")

            def write(self, text: str) -> None:
                super().write(text)
                events.append(f"write:{text}")
                if text.startswith("\r") and "Testing connection..." in text:
                    frames.put(text)

            def flush(self) -> None:
                super().flush()
                events.append("flush")

        class BlockedTester:
            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                events.append("probe")
                case.assertLess(events.index(f"line:{local.provider_id}"), events.index("probe"))
                first_frame = frames.get(timeout=1)
                case.assertIn("Testing connection...", first_frame)
                first_frame_index = events.index(f"write:{first_frame}")
                case.assertEqual("flush", events[first_frame_index - 1])
                case.assertEqual("flush", events[first_frame_index + 1])
                second_frame = frames.get(timeout=1)
                case.assertNotEqual(first_frame, second_frame)
                case.assertTrue(release_probe.wait(timeout=1))
                return ConnectionResult(ConnectionState.READY, "Connection successful")

        output = RecordingOutput()
        release_probe.set()
        outcome = _test_flow(
            local, [local],
            _SetupSession({"local": ProviderStatus(local, "not_required")}, scope=_SetupScope.provider("local")),
            self._store(), BlockedTester(), output, lambda _prompt: "3",
        )

        self.assertEqual("exit", outcome)
        self.assertGreaterEqual(output.flush_count, 3)
        self.assertTrue(any(fragment.startswith("\r") and fragment.strip("\r ") == "" for fragment in output.fragments))

    def test_connection_spinner_uses_ascii_when_the_output_encoding_cannot_render_braille(self) -> None:
        """Terminal compatibility changes glyphs, never the probe or presentation flow."""
        output = _Output()
        output.encoding = "ascii"  # type: ignore[attr-defined]

        with _ConnectionSpinner(output):
            pass

        self.assertIn("\r| Testing connection...", output.fragments)

    def test_connection_spinner_stops_after_a_failed_probe(self) -> None:
        """Failure erases the fixed spinner line before rendering the result."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        output = _Output()

        outcome = _test_flow(
            local, [local],
            _SetupSession({"local": ProviderStatus(local, "not_required")}, scope=_SetupScope.provider("local")),
            self._store(), _Tester(ConnectionResult(ConnectionState.FAILED, "Connection failed")), output,
            lambda _prompt: "3",
        )

        self.assertEqual("exit", outcome)
        erase = next(index for index, fragment in enumerate(output.fragments) if fragment.startswith("\r") and fragment.strip("\r ") == "")
        self.assertTrue(any(line == "✗ Connection failed" for line in output.lines))
        self.assertGreater(output.flush_count, erase)

    def test_connection_spinner_stops_when_the_provider_raises(self) -> None:
        """A provider exception cannot leave the presentation worker running."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        output = _Output()

        class RaisingTester:
            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                raise RuntimeError("safe test exception")

        with self.assertRaisesRegex(RuntimeError, "safe test exception"):
            _test_flow(
                local, [local],
                _SetupSession({"local": ProviderStatus(local, "not_required")}),
                self._store(), RaisingTester(), output, lambda _prompt: "3",
            )

        self.assertTrue(any(fragment.startswith("\r") and fragment.strip("\r ") == "" for fragment in output.fragments))
        self.assertFalse(any(thread.name == "guardrail-connection-spinner" and thread.is_alive() for thread in threading.enumerate()))

    def test_connection_spinner_stops_when_the_probe_is_interrupted(self) -> None:
        """Ctrl+C follows the same worker cleanup path as provider errors."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        output = _Output()

        class InterruptedTester:
            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            _test_flow(
                local, [local],
                _SetupSession({"local": ProviderStatus(local, "not_required")}),
                self._store(), InterruptedTester(), output, lambda _prompt: "3",
            )

        self.assertTrue(any(fragment.startswith("\r") and fragment.strip("\r ") == "" for fragment in output.fragments))
        self.assertFalse(any(thread.name == "guardrail-connection-spinner" and thread.is_alive() for thread in threading.enumerate()))

    def test_test_again_starts_a_second_spinner_worker_before_the_second_probe(self) -> None:
        """Retry uses the same waiting lifecycle rather than a separate path."""
        import queue

        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        frames: queue.Queue[str] = queue.Queue()
        output = _Output()
        case = self

        original_write = output.write

        def capture_frame(text: str) -> None:
            original_write(text)
            if text.startswith("\r") and "Testing connection..." in text:
                frames.put(text)

        output.write = capture_frame  # type: ignore[method-assign]

        class RetryingTester:
            def __init__(self) -> None:
                self.calls = 0

            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                self.calls += 1
                first = frames.get(timeout=1)
                second = frames.get(timeout=1)
                case.assertNotEqual(first, second)
                return ConnectionResult(ConnectionState.READY, "Connection successful")

        tester = RetryingTester()
        outcome = _test_flow(
            local, [local],
            _SetupSession({"local": ProviderStatus(local, "not_required")}, scope=_SetupScope.provider("local")),
            self._store(), tester, output, lambda _prompt, choices=iter(["1", "3"]): next(choices),
        )

        self.assertEqual("exit", outcome)
        self.assertEqual(2, tester.calls)
        self.assertEqual(2, sum(fragment.startswith("\r") and fragment.strip("\r ") == "" for fragment in output.fragments))

    def test_global_test_waiting_screen_keeps_global_result_navigation(self) -> None:
        """Waiting presentation must not alter the global connection-test menu."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        events: list[str] = []

        class EventOutput(_Output):
            def write_line(self, text: str) -> None:
                super().write_line(text)
                if text == "✗ Connection failed":
                    events.append("render_result")

            def write(self, text: str) -> None:
                super().write(text)
                if text.startswith("\r") and "Testing connection..." in text:
                    events.append("render_waiting")

        class FailedTester:
            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                events.append("probe")
                return ConnectionResult(ConnectionState.FAILED, "Connection failed")

        output = EventOutput()
        outcome = _test_flow(
            local, [local], _SetupSession({"local": ProviderStatus(local, "not_required")}),
            self._store(), FailedTester(), output, lambda _prompt: "3",
        )

        self.assertEqual("dashboard", outcome)
        self.assertEqual(["render_waiting", "probe", "render_result"], events)
        self.assertIn("1. Test again", output.text)
        self.assertIn("2. Test another provider", output.text)
        self.assertIn("3. Back to main menu", output.text)
        self.assertNotIn("Back to provider", output.text)
        self.assertNotIn("Exit", output.text)

    def test_provider_test_failure_keeps_scoped_navigation_and_hides_credential(self) -> None:
        """A failed API-key probe keeps the provider menu and never renders its key."""
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        secret = "queued-test-only-credential"
        store = self._store()
        store.set(cloud.provider_id, secret)
        candidates: list[str | None] = []

        class FailedTester:
            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                candidates.append(candidate_credential)
                return ConnectionResult(ConnectionState.FAILED, "Connection failed")

        output = _Output()
        outcome = _test_flow(
            cloud,
            [cloud],
            _SetupSession(
                {"cloud": ProviderStatus(cloud, "configured")},
                scope=_SetupScope.provider("cloud"),
            ),
            store,
            FailedTester(),
            output,
            lambda _prompt: "2",
        )

        self.assertEqual("provider", outcome)
        self.assertEqual([secret], candidates)
        self.assertIn("✗ Connection failed", output.text)
        self.assertIn("2. Back to provider", output.text)
        self.assertIn("3. Exit", output.text)
        self.assertNotIn("Test another provider", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn(secret, output.text)
        self.assertNotIn(secret, "".join(output.fragments))

    def test_windows_pending_input_is_discarded_only_at_the_result_transition(self) -> None:
        """Keys entered during a blocking probe cannot select a result-menu action."""
        terminal_input = _TtyStream()
        keyboard = mock.Mock()
        keyboard.kbhit.side_effect = [True, True, False]
        keyboard.getwch.side_effect = ["7", "\r"]

        with mock.patch("app.cli.sys.stdin", terminal_input), \
             mock.patch("app.cli.os.name", "nt"), \
             mock.patch.dict("sys.modules", {"msvcrt": keyboard}):
            _discard_pending_terminal_input()

        self.assertEqual([mock.call(), mock.call()], keyboard.getwch.call_args_list)

    def test_posix_pending_input_flushes_only_a_tty_queue(self) -> None:
        """POSIX uses the terminal input queue only after a completed probe."""
        terminal_input = mock.Mock()
        terminal_input.isatty.return_value = True
        terminal_input.fileno.return_value = 42
        terminal_api = mock.Mock()
        terminal_api.TCIFLUSH = 7

        with mock.patch("app.cli.sys.stdin", terminal_input), \
             mock.patch("app.cli.os.name", "posix"), \
             mock.patch.dict("sys.modules", {"termios": terminal_api}):
            _discard_pending_terminal_input()

        terminal_api.tcflush.assert_called_once_with(42, 7)

    def test_test_result_dashboard_back_propagates_to_provider_details_parent(self) -> None:
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        output = _Output()
        outcome = _provider_details_screen(
            local, _SetupSession({"local": ProviderStatus(local, "not_required")}), self._store(),
            _Tester(ConnectionResult(ConnectionState.READY, "Connection successful")), _Prompt(), output,
            lambda _prompt, answers=iter(["1", "3"]): next(answers), False, parent="dashboard",
        )
        self.assertEqual("dashboard", outcome)

    def test_credential_result_dashboard_back_propagates_after_retry_test(self) -> None:
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store, output = self._store(), _Output()
        tester = _Tester(
            ConnectionResult(ConnectionState.READY, "Connection successful"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )
        outcome = _credential_flow(
            cloud, False, [cloud], _SetupSession({"cloud": ProviderStatus(cloud, "missing")}), store, tester,
            _Prompt("candidate-only-secret"), output,
            lambda _prompt, answers=iter(["1", "2"]): next(answers),
        )
        self.assertEqual("dashboard", outcome)

    def test_storage_failure_uses_credential_result_screen_before_returning(self) -> None:
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store = mock.Mock()
        store.set.side_effect = LLMConfigurationError("storage unavailable")
        output = _Output()
        outcome = _credential_flow(
            cloud, False, [cloud], _SetupSession({"cloud": ProviderStatus(cloud, "missing")}), store,
            _Tester(ConnectionResult(ConnectionState.READY, "Connection successful")),
            _Prompt("candidate-only-secret"), output, lambda _prompt: "1",
        )
        self.assertEqual("dashboard", outcome)
        self.assertIn("Guardrail Hub — Configure Credential", output.text)
        self.assertIn("Credential storage failed: LLMConfigurationError", output.text)
        self.assertNotIn("storage unavailable", output.text)

    def test_credential_backend_storage_failure_reports_its_safe_reason(self) -> None:
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store = mock.Mock()
        store.set.side_effect = CredentialBackendError(
            "cloud", "unable to establish and verify protected Windows permissions"
        )
        output = _Output()
        candidate = "candidate-only-secret"

        outcome = _credential_flow(
            cloud, False, [cloud], _SetupSession({"cloud": ProviderStatus(cloud, "missing")}), store,
            _Tester(ConnectionResult(ConnectionState.READY, "Connection successful")),
            _Prompt(candidate), output, lambda _prompt: "1",
        )

        self.assertEqual("dashboard", outcome)
        self.assertIn(
            "Credential storage failed: unable to establish and verify protected Windows permissions",
            output.text,
        )
        self.assertNotIn(candidate, output.text)

    def test_invalid_provider_selection_does_not_duplicate_its_rendered_list(self) -> None:
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        output = _Output()
        answers = iter(["bad", "2"])
        _select_and_test(
            [local], _SetupSession({"local": ProviderStatus(local, "not_required")}), self._store(),
            None, output, lambda _prompt: next(answers),
        )
        self.assertEqual(1, output.text.count("1. local"))
        self.assertIn("Invalid selection. Please choose 1 or 2.", output.text)

    def test_nvidia_credential_shortcut_tests_before_persisting_then_refreshes_selected_provider(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output, store = _Output(), self._store()
        secret = "candidate-only-secret"
        tester = _Tester(ConnectionResult(ConnectionState.READY, "Connection successful"))
        code = main(
            ["setup", "--provider", "nvidia-nim", "--credential"],
            credential_store=store,
            secret_prompt=_Prompt(secret),
            connection_tester=tester,
            output=output,
            input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
        )
        self.assertEqual(0, code)
        self.assertEqual([("nvidia-nim", secret)], tester.calls)
        self.assertEqual(secret, store.get("nvidia-nim"))
        self.assertNotIn(secret, output.text)
        self.assertEqual(0, output.text.count("Ready:"))
        self.assertIn("Credential: Configured", output.text.rsplit("Provider Details", maxsplit=1)[1])

    def test_failed_reconfigure_preserves_old_credential(self) -> None:
        store, output = self._store(), _Output()
        store.set("cloud", "old-valid-secret")
        tester = _Tester(ConnectionResult(ConnectionState.FAILED, "Connection failed (safe)"))
        answers = iter(["3", "3"])
        code = main(
            ["setup", "--provider", "cloud", "--reconfigure"],
            credential_store=store,
            secret_prompt=_Prompt("replacement-secret"),
            connection_tester=tester,
            output=output,
            input_reader=lambda _prompt: next(answers),
        )
        self.assertEqual(0, code)
        self.assertEqual("old-valid-secret", store.get("cloud"))
        self.assertEqual(0, output.text.count("Ready:"))
        self.assertNotIn("replacement-secret", output.text)

    def test_failed_candidate_can_retry_without_persisting_the_first_value(self) -> None:
        store, output = self._store(), _Output()
        tester = _Tester(
            ConnectionResult(ConnectionState.FAILED, "Connection failed"),
            ConnectionResult(ConnectionState.READY, "Connection successful"),
        )
        answers = iter(["1", "2", "3"])
        main(
            ["setup", "--provider", "cloud", "--credential"],
            credential_store=store,
            secret_prompt=_Prompt("first-candidate", "second-candidate"),
            connection_tester=tester,
            output=output,
            input_reader=lambda _prompt: next(answers),
        )
        self.assertEqual("second-candidate", store.get("cloud"))
        self.assertEqual([("cloud", "first-candidate"), ("cloud", "second-candidate")], tester.calls)
        self.assertNotIn("first-candidate", output.text)

    def test_provider_menu_reflects_missing_state(self) -> None:
        output = _Output()
        answers = iter(["2"])
        main(["setup", "--provider", "cloud"], credential_store=self._store(), output=output, input_reader=lambda _prompt: next(answers))
        self.assertIn("Credential: Missing", output.text)
        self.assertIn("1. Configure credential", output.text)
        self.assertNotIn("Test connection", output.text)

    def test_provider_details_missing_credential_uses_shared_hidden_entry_flow(self) -> None:
        """The writable details action delegates to the existing credential flow."""
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store, output = self._store(), _Output()
        secret = "details-only-candidate"
        test_case = self
        prompt = _Prompt(secret)

        class _TesterThatChecksPersistence:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str | None]] = []

            def test(self, provider, *, candidate_credential=None) -> ConnectionResult:
                self.calls.append((provider.provider_id, candidate_credential))
                with test_case.assertRaises(CredentialNotFoundError):
                    store.get(provider.provider_id)
                return ConnectionResult(ConnectionState.READY, "Connection successful")

        tester = _TesterThatChecksPersistence()
        with mock.patch("app.cli._credential_flow", wraps=_credential_flow) as credential_flow:
            outcome = _provider_details_screen(
                cloud, _SetupSession({"cloud": ProviderStatus(cloud, "missing")}), store, tester,
                prompt, output, lambda _prompt, answers=iter(["1", "2"]): next(answers),
                False, parent="dashboard",
            )

        self.assertEqual("dashboard", outcome)
        credential_flow.assert_called_once()
        self.assertIn("1. Configure credential", output.text)
        self.assertEqual(["Enter API key:\n> "], prompt.labels)
        self.assertEqual([("cloud", secret)], tester.calls)
        self.assertEqual(secret, store.get("cloud"))
        self.assertNotIn(secret, output.text)

    def test_read_only_provider_details_shows_guidance_without_credential_action(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        result, _ = _load_validated(self.config)
        provider = next(item for item in result.providers if item.provider_id == "nvidia-nim")
        output = _Output()
        outcome = _provider_details_screen(
            provider, _SetupSession({"nvidia-nim": ProviderStatus(provider, "missing")}), self._store(),
            None, _Prompt("must-not-be-read"), output, lambda _prompt: "1", True, parent="dashboard",
        )

        self.assertEqual("dashboard", outcome)
        self.assertIn("Credential: Missing", output.text)
        self.assertIn("running MCP container", output.text)
        self.assertIn("read-only runtime context", output.text)
        self.assertIn("cd mcp-server", output.text)
        self.assertIn("uv run guardrail-hub setup --provider nvidia-nim", output.text)
        self.assertIn("Docker Compose credential provisioning", output.text)
        self.assertNotIn("Configure credential", output.text)
        self.assertNotIn("Enter API key", output.text)

    def test_configured_provider_details_does_not_offer_add_credential(self) -> None:
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        outcome = _provider_details_screen(
            cloud, _SetupSession({"cloud": ProviderStatus(cloud, "configured")}), self._store(),
            None, _Prompt(), output, lambda _prompt: "3", False, parent="dashboard",
        )

        self.assertEqual("dashboard", outcome)
        self.assertIn("Reconfigure credential", output.text)
        self.assertNotIn("Add credential", output.text)

    def test_missing_provider_details_uses_its_rendered_two_action_range(self) -> None:
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        _provider_details_screen(
            cloud, _SetupSession({"cloud": ProviderStatus(cloud, "missing")}), self._store(),
            None, _Prompt(), output, lambda _prompt, answers=iter(["bad", "3", "2"]): next(answers),
            False, parent="dashboard",
        )

        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1 or 2."))

    def test_unknown_provider_offers_config_boundary_guidance(self) -> None:
        output = _Output()
        code = main(["setup", "--provider", "absent"], credential_store=self._store(), output=output, input_reader=lambda _prompt: "3")
        self.assertEqual(3, code)
        self.assertEqual("GuardrailHub: unknown provider 'absent'.", output.lines[0])
        self.assertIn("Available providers:", output.text)
        self.assertIn("- local", output.text)
        self.assertIn("- cloud", output.text)
        self.assertIn("- disabled", output.text)
        self.assertIn("guardrail-hub config apply <llm.yaml>", output.text)

    def test_unknown_provider_shortcuts_reject_before_provisioning_resolution(self) -> None:
        first_lines: list[str] = []
        for shortcut in ([], ["--credential"], ["--reconfigure"]):
            with self.subTest(shortcut=shortcut):
                output = _Output()
                prompt = _Prompt("must-not-be-read")
                tester = _Tester(ConnectionResult(ConnectionState.READY))
                with mock.patch("app.cli._resolve_store", return_value=(self._store(), False, False)) as resolve:
                    code = main(
                        ["setup", "--provider", "nvidia-ni", *shortcut],
                        secret_prompt=prompt,
                        connection_tester=tester,
                        output=output,
                        input_reader=lambda _prompt: "4",
                    )

                self.assertEqual(3, code)
                resolve.assert_not_called()
                self.assertEqual(0, prompt.calls)
                self.assertEqual([], tester.calls)
                first_lines.append(output.lines[0])
                self.assertEqual("GuardrailHub: unknown provider 'nvidia-ni'.", output.lines[0])
                self.assertIn("Available providers:", output.text)
                self.assertIn("local", output.text)
                self.assertIn("cloud", output.text)
                self.assertNotIn("Guardrail Hub — LLM Setup", output.text)
        self.assertEqual(
            ["GuardrailHub: unknown provider 'nvidia-ni'."] * 3,
            first_lines,
        )

    def test_known_disabled_provider_is_not_unknown(self) -> None:
        output = _Output()
        code = main(
            ["setup", "--provider", "disabled"],
            credential_store=self._store(),
            output=output,
            input_reader=lambda _prompt: "1",
        )

        self.assertEqual(0, code)
        self.assertNotIn("is not configured", output.text)
        self.assertIn("disabled", output.text)

    def test_missing_provider_menu_never_forces_configuration(self) -> None:
        output = _Output()
        answers = iter(["1", "2", "4"])
        main(["setup"], credential_store=self._store(), output=output, input_reader=lambda _prompt: next(answers))
        self.assertIn("1. cloud", output.text)
        self.assertIn("2. Back", output.text)

    def test_writable_missing_provider_is_listed_for_credential_setup(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output, store = _Output(), self._store()
        answers = iter(["1", "1", "2", "4"])
        main(
            ["setup"],
            credential_store=store,
            secret_prompt=_Prompt("candidate-only-secret"),
            connection_tester=_Tester(ConnectionResult(ConnectionState.READY, "Connection successful")),
            output=output,
            input_reader=lambda _prompt: next(answers),
        )
        self.assertIn("1. nvidia-nim", output.text)
        self.assertEqual("candidate-only-secret", store.get("nvidia-nim"))

    def test_read_only_missing_credential_does_not_offer_add_action(self) -> None:
        result, _ = _load_validated(self.config)
        provider = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        _main_menu(
            _SetupSession({"cloud": ProviderStatus(provider, "missing")}),
            self._store(), None, _Prompt(), output, lambda _prompt: "2", True,
        )
        self.assertNotIn("Add credentials for missing providers", output.text)
        self.assertIn("read-only runtime context", output.text)

    def test_read_only_context_does_not_offer_reconfigure_action(self) -> None:
        result, _ = _load_validated(self.config)
        provider = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        _main_menu(
            _SetupSession({"cloud": ProviderStatus(provider, "configured")}),
            self._store(), None, _Prompt(), output, lambda _prompt: "3", True,
        )
        self.assertNotIn("Reconfigure configured providers", output.text)
        self.assertIn("read-only runtime context", output.text)

    def test_read_only_menu_keeps_test_and_details_actions_separate_from_mutation(self) -> None:
        """A missing read-only credential must not hide useful provider operations."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        answers = iter(["1", "2", "2", "3", "3"])

        _main_menu(
            _SetupSession({
                "local": ProviderStatus(local, "not_required"),
                "cloud": ProviderStatus(cloud, "missing"),
            }),
            self._store(), _Tester(ConnectionResult(ConnectionState.READY)), _Prompt(),
            output, lambda _prompt: next(answers), True,
        )

        self.assertNotIn("Add credentials for missing providers", output.text)
        self.assertNotIn("Reconfigure configured providers", output.text)
        self.assertIn("1. Test provider connections", output.text)
        self.assertIn("2. View provider details", output.text)
        self.assertIn("3. Exit", output.text)
        self.assertIn("1. local", output.text)
        self.assertNotIn("2. cloud\n2. Back", output.text)
        self.assertIn("1. local\n2. cloud\n3. Back", output.text)

    def test_read_only_configured_api_key_provider_remains_testable(self) -> None:
        """Read-only changes mutation capability, not a resolvable credential's testability."""
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        store = self._store()
        store.set("cloud", "stored-test-only-credential")
        tester = _Tester(ConnectionResult(ConnectionState.READY))
        output = _Output()
        answers = iter(["1", "1", "3", "3"])

        _main_menu(
            _SetupSession({"cloud": ProviderStatus(cloud, "externally_managed")}),
            store, tester, _Prompt(), output, lambda _prompt: next(answers), True,
        )

        self.assertNotIn("Reconfigure configured providers", output.text)
        self.assertIn("Test provider connections", output.text)
        self.assertEqual([("cloud", "stored-test-only-credential")], tester.calls)

    def test_read_only_menu_hides_test_when_no_provider_can_be_tested_but_keeps_details(self) -> None:
        """A missing API-key provider is viewable even when it cannot be tested."""
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        answers = iter(["1", "1", "1", "2", "2"])

        _main_menu(
            _SetupSession({"cloud": ProviderStatus(cloud, "missing")}),
            self._store(), None, _Prompt(), output, lambda _prompt: next(answers), True,
        )

        self.assertNotIn("Test provider connections", output.text)
        self.assertIn("1. View provider details", output.text)
        self.assertIn("2. Exit", output.text)
        self.assertIn("Status: Missing credential", output.text)

    def test_read_only_credential_shortcut_stays_in_provider_session(self) -> None:
        """A read-only shortcut explains the boundary without ending useful navigation."""
        output = _Output()
        prompt = _Prompt("must-not-be-read")
        with mock.patch("app.cli._resolve_store", return_value=(self._store(), True, False)):
            code = main(
                ["setup", "--provider", "cloud", "--credential"],
                secret_prompt=prompt,
                output=output,
                input_reader=lambda _prompt, answers=iter(["1", "1"]): next(answers),
            )

        self.assertEqual(0, code)
        self.assertEqual(0, prompt.calls)
        self.assertIn("Credential: Missing", output.text)
        self.assertIn("Credential changes are unavailable", output.text)
        self.assertIn("1. Exit", output.text.rsplit("Provider Details", maxsplit=1)[1])
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)
        self.assertIn("read-only runtime context", output.text)

    def test_dynamic_read_only_menu_reports_its_rendered_range(self) -> None:
        """Invalid input must use the three-action range, not a stale credential-only range."""
        result, _ = _load_validated(self.config)
        local = next(item for item in result.providers if item.provider_id == "local")
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        answers = iter(["bad", "9", "3"])

        _main_menu(
            _SetupSession({
                "local": ProviderStatus(local, "not_required"),
                "cloud": ProviderStatus(cloud, "missing"),
            }),
            self._store(), None, _Prompt(), output, lambda _prompt: next(answers), True,
        )

        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1, 2, or 3."))

    def test_read_only_credential_shortcut_explains_host_provisioning(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()
        prompt = _Prompt("must-not-be-read")
        with mock.patch("app.cli._resolve_store", return_value=(self._store(), True, False)):
            code = main(
                ["setup", "--provider", "nvidia-nim", "--credential"],
                secret_prompt=prompt,
                output=output,
                input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
            )
        self.assertEqual(0, code)
        self.assertEqual(0, prompt.calls)
        self.assertIn("running MCP container", output.text)
        self.assertIn("read-only runtime context", output.text)
        self.assertIn("cd mcp-server", output.text)
        self.assertIn("uv run guardrail-hub setup --provider nvidia-nim", output.text)
        self.assertIn("Docker Compose credential provisioning", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_read_only_reconfigure_shortcut_explains_host_provisioning(self) -> None:
        self.config.write_text(_CONFIG.replace("id: cloud", "id: nvidia-nim"), encoding="utf-8")
        output = _Output()
        prompt = _Prompt("must-not-be-read")
        store = self._store()
        store.set("nvidia-nim", "configured-only-for-test")
        with mock.patch("app.cli._resolve_store", return_value=(store, True, False)):
            code = main(
                ["setup", "--provider", "nvidia-nim", "--reconfigure"],
                secret_prompt=prompt,
                output=output,
                input_reader=lambda _prompt, answers=iter(["2", "3"]): next(answers),
            )
        self.assertEqual(0, code)
        self.assertEqual(0, prompt.calls)
        self.assertIn("running MCP container", output.text)
        self.assertIn("uv run guardrail-hub setup --provider nvidia-nim", output.text)
        self.assertNotIn("Back to main menu", output.text)
        self.assertNotIn("Guardrail Hub — LLM Setup", output.text)

    def test_credential_shortcut_rejects_ineligible_provider_states_without_prompting(self) -> None:
        self.config.write_text(_CONFIG + _AWS_PROVIDER, encoding="utf-8")
        cases = (
            ("disabled", self._store(), False, "provider is disabled"),
            ("local", self._store(), False, "does not require an API key"),
            ("bedrock", self._store(), False, "AWS SDK credential chain"),
            ("cloud", self._configured_store("cloud"), False, "already configured"),
            ("cloud", self._store(), True, "read-only runtime context"),
            ("cloud", self._configured_store("cloud"), True, "read-only runtime context"),
        )

        for provider_id, store, read_only, expected in cases:
            with self.subTest(provider_id=provider_id, read_only=read_only):
                output = _Output()
                prompt = _Prompt("must-not-be-read")
                resolve = mock.patch("app.cli._resolve_store", return_value=(store, read_only, False))
                with resolve:
                    code = main(
                        ["setup", "--provider", provider_id, "--credential"],
                        secret_prompt=prompt,
                        aws_detector=_AwsDetector(),
                        connection_tester=_Tester(ConnectionResult(ConnectionState.READY)),
                        output=output,
                        input_reader=self._choose_last,
                    )
                self.assertEqual(0, code)
                self.assertEqual(0, prompt.calls)
                self.assertIn(expected, output.text)
                if read_only:
                    shortcut_screen = output.text.split("Guardrail Hub — LLM Setup", maxsplit=1)[0]
                    self.assertIn("read-only runtime context", shortcut_screen)

    def test_reconfigure_shortcut_rejects_ineligible_provider_states_without_prompting(self) -> None:
        self.config.write_text(_CONFIG + _AWS_PROVIDER, encoding="utf-8")
        read_only_store = self._configured_store("cloud")
        cases = (
            ("cloud", self._store(), False, "credential is missing"),
            ("disabled", self._store(), False, "provider is disabled"),
            ("local", self._store(), False, "does not require an API key"),
            ("bedrock", self._store(), False, "AWS SDK credential chain"),
            ("cloud", read_only_store, True, "read-only runtime context"),
            ("cloud", self._store(), True, "read-only runtime context"),
        )

        for provider_id, store, read_only, expected in cases:
            with self.subTest(provider_id=provider_id, read_only=read_only):
                output = _Output()
                prompt = _Prompt("must-not-be-read")
                resolve = mock.patch("app.cli._resolve_store", return_value=(store, read_only, False))
                with resolve:
                    code = main(
                        ["setup", "--provider", provider_id, "--reconfigure"],
                        secret_prompt=prompt,
                        aws_detector=_AwsDetector(),
                        connection_tester=_Tester(ConnectionResult(ConnectionState.READY)),
                        output=output,
                        input_reader=self._choose_last,
                    )
                self.assertEqual(0, code)
                self.assertEqual(0, prompt.calls)
                self.assertIn(expected, output.text)
                if read_only:
                    shortcut_screen = output.text.split("Guardrail Hub — LLM Setup", maxsplit=1)[0]
                    self.assertIn("read-only runtime context", shortcut_screen)

    def test_read_only_guidance_does_not_render_an_unsafe_provider_id_as_shell_code(self) -> None:
        provider_id = "unsafe; Write-Output compromised"
        output = _Output()

        _render_external_credential_guidance(provider_id, output)

        self.assertNotIn(f"--provider {provider_id}", output.text)
        self.assertIn("cannot be rendered safely in a shell command", output.text)

    def test_env_managed_read_only_guidance_does_not_claim_compose_or_container(self) -> None:
        result, _ = _load_validated(self.config)
        cloud = next(item for item in result.providers if item.provider_id == "cloud")
        output = _Output()
        with mock.patch.dict(
            os.environ, {"GUARDRAILHUB_CREDENTIAL_BACKEND": "env"}, clear=False,
        ), mock.patch("sys.platform", "linux"), mock.patch(
            "app.intelligence.setup.compose_host.recognize_compose_host_project", return_value=None,
        ):
            store, read_only_context, failed = _resolve_store(
                self.config, output, self._choose_last, None,
            )

        self.assertFalse(failed)
        _main_menu(
            _SetupSession({"cloud": ProviderStatus(cloud, "missing")}),
            store, None, _Prompt(), output, self._choose_last, read_only_context,
        )
        self.assertIn("read-only runtime context", output.text)
        self.assertIn("deployment environment", output.text)
        self.assertNotIn("running MCP container", output.text)
        self.assertNotIn("Docker Compose credential provisioning", output.text)

    def test_main_menu_rejects_malformed_and_out_of_range_selection(self) -> None:
        output = _Output()
        answers = iter(["not-a-number", "9", "4"])
        main(["setup"], credential_store=self._store(), output=output, input_reader=lambda _prompt: next(answers))
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1, 2, 3, or 4."))

    def test_provider_selection_retries_invalid_input(self) -> None:
        output = _Output()
        answers = iter(["1", "nope", "9", "2", "4"])
        main(["setup"], credential_store=self._store(), output=output, input_reader=lambda _prompt: next(answers))
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1 or 2."))

    def test_provider_menu_retries_invalid_input(self) -> None:
        output = _Output()
        answers = iter(["wrong", "9", "2", "4"])
        main(["setup", "--provider", "cloud"], credential_store=self._store(), output=output, input_reader=lambda _prompt: next(answers))
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1 or 2."))

    def test_retry_menu_retries_invalid_input(self) -> None:
        output = _Output()
        answers = iter(["wrong", "9", "4"])
        main(
            ["setup", "--provider", "cloud", "--credential"],
            credential_store=self._store(), secret_prompt=_Prompt("candidate-only-secret"),
            connection_tester=_Tester(ConnectionResult(ConnectionState.FAILED, "Connection failed")),
            output=output, input_reader=lambda _prompt: next(answers),
        )
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1, 2, 3, or 4."))

    def test_environment_choice_retries_invalid_input(self) -> None:
        from app.intelligence.setup.compose_host import ComposeHostProject

        output = _Output()
        answers = iter(["wrong", "9", "2"])
        prompts: list[str] = []
        with mock.patch("sys.platform", "win32"), \
             mock.patch("app.intelligence.setup.compose_host.recognize_compose_host_project", return_value=ComposeHostProject(self.config.parent.parent, self.config.parent.parent / "secrets")), \
             mock.patch("app.intelligence.credentials.backend_factory.build_credential_backend", return_value=InMemoryCredentialBackend()):
            store, _external, failed = _resolve_store(
                self.config, output, lambda prompt: prompts.append(prompt) or next(answers), None,
            )
        self.assertFalse(failed)
        self.assertIn("ComposeHostCredentialProvisioner", repr(store))
        self.assertIn("Where should this credential be provisioned?", output.text)
        self.assertIn("1. Windows local credential store", output.text)
        self.assertIn("2. Docker Compose credential provisioning", output.text)
        self.assertEqual(["Select [1-2]: "] * 3, prompts)
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1 or 2."))

    def test_recognized_compose_host_keeps_missing_provider_configurable(self) -> None:
        from app.intelligence.setup.compose_host import ComposeHostProject

        output = _Output()
        project = ComposeHostProject(self.config.parent.parent, self.config.parent.parent / "secrets")
        with mock.patch("sys.platform", "linux"), \
             mock.patch("app.intelligence.setup.compose_host.recognize_compose_host_project", return_value=project):
            _store, external, failed = _resolve_store(self.config, output, lambda _prompt: "1", None)
        self.assertFalse(failed)
        self.assertFalse(external)

    def test_success_menu_retries_invalid_input(self) -> None:
        output = _Output()
        answers = iter(["wrong", "9", "3"])
        main(
            ["setup", "--provider", "cloud", "--credential"],
            credential_store=self._store(), secret_prompt=_Prompt("candidate-only-secret"),
            connection_tester=_Tester(ConnectionResult(ConnectionState.READY, "Connection successful")),
            output=output, input_reader=lambda _prompt: next(answers),
        )
        self.assertEqual(2, output.text.count("Invalid selection. Please choose 1, 2, or 3."))

    def test_keyboard_interrupt_cancels_setup_without_traceback(self) -> None:
        output = _Output()
        def interrupted(_prompt: str) -> str:
            raise KeyboardInterrupt
        code = main(["setup"], credential_store=self._store(), output=output, input_reader=interrupted)
        self.assertEqual(0, code)
        self.assertIn("Setup cancelled.", output.text)

    def test_eof_cancels_setup_without_traceback(self) -> None:
        output = _Output()
        def closed(_prompt: str) -> str:
            raise EOFError
        code = main(["setup"], credential_store=self._store(), output=output, input_reader=closed)
        self.assertEqual(0, code)
        self.assertIn("Setup cancelled.", output.text)

    def test_interactive_setup_restores_the_original_screen_after_cancellation(self) -> None:
        """Ctrl+C and EOF leave alternate mode before returning to the shell."""
        for interruption in (KeyboardInterrupt, EOFError):
            terminal = _TtyStream()
            with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}), \
                 mock.patch("app.cli.sys.stdout", terminal), mock.patch("app.cli.sys.stdin", _TtyStream()):
                code = main(
                    ["setup"], credential_store=self._store(),
                    input_reader=lambda _prompt, error=interruption: (_ for _ in ()).throw(error()),
                )
            self.assertEqual(0, code)
            self.assertIn("Setup cancelled.", terminal.getvalue())
            self.assertIn("\x1b[?1049h", terminal.getvalue())
            self.assertIn("\x1b[?25h\x1b[?1049lSetup cancelled.", terminal.getvalue())

    def test_interactive_setup_restores_the_original_screen_after_unexpected_failure(self) -> None:
        terminal = _TtyStream()
        with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}), \
             mock.patch("app.cli.sys.stdout", terminal), mock.patch("app.cli.sys.stdin", _TtyStream()), \
             mock.patch("app.cli._run_setup", side_effect=RuntimeError("unexpected")):
            code = main(["setup"], credential_store=self._store())
        self.assertEqual(3, code)
        self.assertIn("\x1b[?25h\x1b[?1049lSetup error: RuntimeError", terminal.getvalue())

    def test_hidden_credential_prompt_cancellation_is_clean(self) -> None:
        class CancelledPrompt:
            def read_secret(self, _label: str) -> str:
                raise KeyboardInterrupt

        output = _Output()
        code = main(
            ["setup", "--provider", "cloud", "--credential"],
            credential_store=self._store(),
            secret_prompt=CancelledPrompt(),
            output=output,
        )
        self.assertEqual(0, code)
        self.assertIn("Setup cancelled.", output.text)

    def test_hidden_secure_input_cancellation_and_eof_are_clean(self) -> None:
        """Terminal cancellation from the real secure-input adapter must not traceback."""
        for interruption in (KeyboardInterrupt, EOFError):
            with self.subTest(interruption=interruption.__name__):
                class InterruptedPrompt:
                    def read_secret(_self, _prompt_text: str) -> str:
                        raise interruption

                output = _Output()
                code = main(
                    ["setup", "--provider", "cloud", "--credential"],
                    credential_store=self._store(),
                    secret_prompt=InterruptedPrompt(),
                    output=output,
                )

                self.assertEqual(0, code)
                self.assertIn("Setup cancelled.", output.text)

    def test_default_masked_prompt_fails_closed_without_an_interactive_terminal(self) -> None:
        """A redirected terminal must never degrade to a visible credential prompt."""
        output = _Output()
        with mock.patch("app.cli.sys.stdin", io.StringIO()), mock.patch("app.cli.sys.stdout", io.StringIO()):
            code = main(
                ["setup", "--provider", "cloud", "--credential"],
                credential_store=self._store(), output=output,
            )
        self.assertEqual(3, code)
        self.assertIn("secure credential entry requires an interactive terminal", output.text)

    def test_backend_inspection_failure_is_a_safe_distinct_dashboard_state(self) -> None:
        class BrokenBackend:
            def get(self, provider_id: str) -> str:
                raise CredentialBackendError(provider_id, "backend unavailable")

            def set(self, _provider_id: str, _credential: str) -> None:
                raise AssertionError("must not persist")

        output = _Output()
        code = main(["setup"], credential_store=CredentialStore(BrokenBackend()), output=output, input_reader=lambda _prompt: "3")
        self.assertEqual(0, code)
        self.assertIn("Credential inspection unavailable", output.text)
        self.assertNotIn("Missing credential", output.text)
        self.assertNotIn("backend unavailable", output.text)


class ConfigCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.current = Path(self.directory.name) / "llm.yaml"
        self.current.write_text(_CONFIG, encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"REGISTRY_LLM_CONFIG_PATH": str(self.current)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_show_is_safe_and_validate_is_non_mutating(self) -> None:
        output = _Output()
        self.assertEqual(0, main(["config", "show"], output=output))
        self.assertIn("cloud: type=openai_compatible", output.text)
        self.assertNotIn("CLOUD_KEY=", output.text)
        before = self.current.read_bytes()
        candidate = Path(self.directory.name) / "candidate.yaml"
        candidate.write_text(_CONFIG.replace("enabled: true", "enabled: false", 1), encoding="utf-8")
        self.assertEqual(0, main(["config", "validate", str(candidate)], output=_Output()))
        self.assertEqual(before, self.current.read_bytes())

    def test_apply_requires_confirmation_and_replaces_only_after_yes(self) -> None:
        candidate = Path(self.directory.name) / "candidate.yaml"
        candidate.write_text(_CONFIG.replace("enabled: true", "enabled: false", 1), encoding="utf-8")
        output = _Output()
        self.assertEqual(0, main(["config", "apply", str(candidate)], output=output, input_reader=lambda _prompt: "yes"))
        self.assertIn("Provider changed: local (enabled)", output.text)
        self.assertEqual(candidate.read_bytes(), self.current.read_bytes())

    def test_apply_fails_closed_without_interactive_input(self) -> None:
        candidate = Path(self.directory.name) / "candidate.yaml"
        candidate.write_text(_CONFIG, encoding="utf-8")
        with mock.patch("sys.stdin.isatty", return_value=False):
            self.assertEqual(3, main(["config", "apply", str(candidate)], output=_Output()))

    def test_apply_failure_preserves_current_configuration(self) -> None:
        candidate = Path(self.directory.name) / "candidate.yaml"
        candidate.write_text(_CONFIG.replace("enabled: true", "enabled: false", 1), encoding="utf-8")
        before = self.current.read_bytes()
        with mock.patch("app.cli._atomic_replace", side_effect=OSError("replace failed")):
            code = main(["config", "apply", str(candidate)], output=_Output(), input_reader=lambda _prompt: "yes")
        self.assertEqual(2, code)
        self.assertEqual(before, self.current.read_bytes())
