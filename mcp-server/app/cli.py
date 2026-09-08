"""Operator CLI for configured LLM providers and llm.yaml topology."""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Sequence, TextIO

from app.intelligence.credentials import (
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialStore,
)
from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.registry.exceptions import RegistryLoadError
from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader
from app.intelligence.registry.models.provider import AuthType, ProviderRecord
from app.intelligence.setup.connection import ConnectionState, ProviderConnectionTester
from app.intelligence.setup.ports import AwsCredentialDetector, OutputWriter, SecretPrompt

_EXIT_OK, _EXIT_CONFIG_ERROR, _EXIT_SETUP_ERROR = 0, 2, 3
_PROG = "guardrail-hub"


class _ArgumentParser(argparse.ArgumentParser):
    """Keep rejected command-line credential values out of operator output."""

    def error(self, message: str) -> None:
        contains_credential_argument = "credential" in message or "api-key" in message
        if message.startswith("unrecognized arguments:") or (
            contains_credential_argument and "require --provider" not in message
        ):
            self.exit(
                2,
                f"{self.prog}: error: credential values are not accepted on the command line. "
                "Credentials are entered securely when prompted.\n",
            )
        super().error(message)


class _AlternateScreen:
    """Temporarily isolate interactive setup output from the calling shell."""

    _ENTER = "\x1b[?1049h\x1b[H\x1b[?25h"
    _LEAVE = "\x1b[?25h\x1b[?1049l"
    _REDRAW = "\x1b[2J\x1b[H"

    def __init__(self, output: TextIO, input_stream: TextIO, *, term: str | None = None) -> None:
        self._output = output
        self._active = self._supported(input_stream, output, term)
        self._entered = False

    @staticmethod
    def _supported(input_stream: TextIO, output: TextIO, term: str | None) -> bool:
        if not input_stream.isatty() or not output.isatty():
            return False
        normalized_term = (term if term is not None else os.environ.get("TERM", "")).lower()
        if normalized_term == "dumb":
            return False
        return bool(normalized_term or os.environ.get("WT_SESSION") or os.environ.get("ConEmuANSI"))

    def __enter__(self) -> "_AlternateScreen":
        if self._active:
            self._output.write(self._ENTER)
            self._output.flush()
            self._entered = True
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> bool:
        if self._active:
            self._output.write(self._LEAVE)
            self._output.flush()
            self._entered = False
        return False

    def redraw(self) -> None:
        """Clear the active alternate screen before a real screen transition."""
        if self._entered:
            self._output.write(self._REDRAW)
            self._output.flush()


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    provider: ProviderRecord
    credential: str
    connection: ConnectionState = ConnectionState.NOT_TESTED


class _CredentialMutationAction(str, Enum):
    CONFIGURE = "configure"
    RECONFIGURE = "reconfigure"


class _ReadOnlyCredentialContext(str, Enum):
    CONTAINER_FILE = "container_file"
    ENVIRONMENT = "environment"


class _CredentialMutationBlocker(str, Enum):
    DISABLED = "disabled"
    NO_AUTH = "no_auth"
    AWS_AUTH = "aws_auth"
    ALREADY_CONFIGURED = "already_configured"
    MISSING = "missing"
    READ_ONLY = "read_only"
    UNAVAILABLE_STATE = "unavailable_state"


@dataclass(frozen=True, slots=True)
class _CredentialMutationEligibility:
    action: _CredentialMutationAction
    blocker: _CredentialMutationBlocker | None = None

    @property
    def allowed(self) -> bool:
        return self.blocker is None


@dataclass(slots=True)
class _SetupSession:
    statuses: dict[str, ProviderStatus]
    changed: bool = False
    redraw: Callable[[], None] = lambda: None
    has_screen: bool = False

    def show_screen(self) -> None:
        """Redraw only when replacing an already-rendered setup screen."""
        if self.has_screen:
            self.redraw()
        self.has_screen = True


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog=_PROG, description="Guardrail Hub operator CLI.")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser(
        "setup",
        help="Operate configured provider credentials and readiness.",
        description="Inspect configured provider readiness and securely manage credentials.",
        epilog=(
            "Examples:\n"
            "  guardrail-hub setup\n"
            "  guardrail-hub setup --provider nvidia-nim\n"
            "  guardrail-hub setup --provider nvidia-nim --credential\n"
            "  guardrail-hub setup --provider nvidia-nim --reconfigure\n\n"
            "Credentials are entered securely when prompted.\n"
            "Never pass API keys on the command line."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    setup.add_argument("--provider", metavar="PROVIDER_ID")
    credential_action = setup.add_mutually_exclusive_group()
    credential_action.add_argument("--credential", action="store_true", help="Configure a missing credential for --provider.")
    credential_action.add_argument("--reconfigure", action="store_true", help="Replace a credential for --provider after validation.")
    return parser


def main(argv: Optional[Sequence[str]] = None, *, credential_store: Optional[CredentialStore] = None,
         secret_prompt: Optional[SecretPrompt] = None, aws_detector: Optional[AwsCredentialDetector] = None,
         output: Optional[OutputWriter] = None, input_reader: Optional[Callable[[str], str]] = None,
         connection_tester: Optional[ProviderConnectionTester] = None) -> int:
    args = _build_parser().parse_args(argv)
    from app.intelligence.setup.adapters import Boto3AwsCredentialDetector, MaskedSecretPrompt, SecureInputUnavailableError, StreamOutputWriter
    out, prompt, detector, reader = output or StreamOutputWriter(), secret_prompt or MaskedSecretPrompt(), aws_detector or Boto3AwsCredentialDetector(), input_reader or input
    try:
        if (args.credential or args.reconfigure) and not args.provider:
            _build_parser().error("--credential and --reconfigure require --provider")
        # Parsing completes before this point, so help and parser errors never
        # alter the terminal.  The context manager restores the caller's
        # screen even when setup is cancelled or fails unexpectedly.
        with _AlternateScreen(sys.stdout, sys.stdin) as terminal:
            return _run_setup(args, out, prompt, detector, reader, credential_store, connection_tester, terminal.redraw)
    except SecureInputUnavailableError:
        out.write_line("Setup error: secure credential entry requires an interactive terminal.")
        return _EXIT_SETUP_ERROR
    except (KeyboardInterrupt, EOFError):
        out.write_line("Setup cancelled.")
        return _EXIT_OK
    except Exception as exc:  # noqa: BLE001 - setup must restore a usable terminal.
        out.write_line(f"Setup error: {type(exc).__name__}")
        return _EXIT_SETUP_ERROR


def _current_config_path() -> Path:
    """Resolve only this setting, without importing full application Settings."""
    return Path(os.environ.get("REGISTRY_LLM_CONFIG_PATH", "config/llm.yaml"))
def _load_validated(path: Path):
    """Load the configured-provider topology used by setup screens."""
    result = LLmConfigLoader().load(path)
    if result.errors:
        from app.intelligence.registry.exceptions import LoadIssue, LoadReport
        raise RegistryLoadError(
            LoadReport(
                issues=tuple(
                    LoadIssue(file_path=str(path), position="(root)", message=error)
                    for error in result.errors
                )
            )
        )
    return result, None

def _run_setup(args, out, prompt, detector, reader, injected_store, injected_tester, redraw: Callable[[], None] = lambda: None) -> int:
    current = _current_config_path()
    try:
        result = LLmConfigLoader().load(current)
    except RegistryLoadError as exc:
        out.write_line("Configuration error: unable to load LLM configuration.")
        out.write_line(str(exc))
        return _EXIT_CONFIG_ERROR
    if result.errors:
        out.write_line(f"Configuration error: llm.yaml is invalid ({len(result.errors)} issue(s)):")
        for error in result.errors:
            out.write_line(f"  - {error}")
        return _EXIT_CONFIG_ERROR
    store, external, failed = _resolve_store(current, out, reader, injected_store)
    if failed: return _EXIT_SETUP_ERROR
    # Adapter imports are intentionally lazy. A dashboard or an unknown-provider
    # error must not import optional SDKs or construct the application runtime.
    tester = injected_tester
    try:
        session = _SetupSession(_inspect(result.providers, store, detector, external), redraw=redraw)
    except LLMConfigurationError as exc:
        out.write_line(f"Setup error: credential inspection failed ({type(exc).__name__})")
        return _EXIT_SETUP_ERROR
    if args.provider:
        provider = next((p for p in result.providers if p.provider_id == args.provider), None)
        if provider is None: _unknown_provider(args.provider, out); return _EXIT_SETUP_ERROR
        if args.credential or args.reconfigure:
            _credential_flow(
                provider, args.reconfigure, [provider], session, store, tester, prompt, out, reader,
                read_only=external,
            )
        else:
            _provider_details_screen(provider, session, store, tester, prompt, out, reader, external, parent="dashboard")
    _main_menu(session, store, tester, prompt, out, reader, external)
    return _EXIT_OK


def _resolve_store(current, out, reader, injected):
    if injected is not None: return injected, False, False
    from app.intelligence.credentials.backend_factory import build_credential_backend, build_provider_env_var_names
    from app.intelligence.credentials.container_backend import ContainerFileCredentialBackend
    from app.intelligence.credentials.env_backend import EnvVarCredentialBackend
    from app.intelligence.setup.compose_host import ComposeHostCredentialProvisioner, recognize_compose_host_project
    compose = recognize_compose_host_project(current)
    try:
        if compose and sys.platform != "win32": return CredentialStore(ComposeHostCredentialProvisioner(compose)), False, False
        if compose and sys.platform == "win32":
            if not sys.stdin.isatty() and reader is input:
                out.write_line("Setup error: Windows local and Compose host contexts are both possible; run interactively to choose the deployment context."); return None, False, True
            out.write_line("Where should this credential be provisioned?")
            out.write_line("")
            out.write_line("1. Windows local credential store")
            out.write_line("2. Docker Compose credential provisioning")
            out.write_line("")
            while True:
                choice = _read_selection(
                    reader, out,
                    2,
                )
                if choice is None:
                    continue
                if choice == 2:
                    return CredentialStore(ComposeHostCredentialProvisioner(compose)), False, False
                break
        records, _ = _load_validated(current)
        backend = build_credential_backend(env_var_names=build_provider_env_var_names(records.providers))
        read_only_context: _ReadOnlyCredentialContext | bool = False
        if isinstance(backend, ContainerFileCredentialBackend):
            read_only_context = _ReadOnlyCredentialContext.CONTAINER_FILE
        elif isinstance(backend, EnvVarCredentialBackend):
            read_only_context = _ReadOnlyCredentialContext.ENVIRONMENT
        return CredentialStore(backend), read_only_context, False
    except LLMConfigurationError as exc:
        out.write_line(f"Setup error: {exc}"); return None, False, True


class _UnsupportedConnectionTester:
    def test(self, _provider, *, candidate_credential=None):
        from app.intelligence.setup.connection import ConnectionResult
        return ConnectionResult(ConnectionState.UNSUPPORTED, "Connection test unsupported")


def _default_tester(provider: ProviderRecord):
    """Build exactly the selected adapter, avoiding full-registry bootstrap."""
    from app.intelligence.providers.provider_factory import ProviderFactory
    factory = ProviderFactory()
    provider_type = provider.provider_type.value
    if provider_type == "ollama":
        from app.intelligence.providers.adapters.ollama import OllamaAdapter
        factory.register(provider_type, OllamaAdapter)
    elif provider_type == "openai_compatible":
        from app.intelligence.providers.adapters.openai_compatible import OpenAICompatibleAdapter
        factory.register(provider_type, OpenAICompatibleAdapter)
    elif provider_type == "bedrock":
        try:
            from app.intelligence.providers.adapters.bedrock import BedrockAdapter
        except ModuleNotFoundError:
            return _UnsupportedConnectionTester()
        factory.register(provider_type, BedrockAdapter)
    else:
        return _UnsupportedConnectionTester()
    return ProviderConnectionTester(factory=factory)


def _inspect(providers, store, detector, external):
    statuses = {}
    for provider in providers:
        credential = "not_required"
        if provider.enabled and provider.auth.type is AuthType.AWS: credential = "aws_detected" if detector.is_available() else "missing"
        elif provider.enabled and provider.auth.type is AuthType.API_KEY:
            try: store.get(provider.provider_id); credential = "configured"
            except CredentialNotFoundError: credential = "missing"
        statuses[provider.provider_id] = ProviderStatus(provider, credential)
    return statuses


def _authentication_label(provider: ProviderRecord) -> str:
    if provider.auth.type is AuthType.API_KEY:
        return "API Key"
    if provider.auth.type is AuthType.AWS:
        return "AWS Credentials"
    return "None"


def _provider_status_label(status: ProviderStatus) -> tuple[str, str]:
    if not status.provider.enabled:
        return "–", "Disabled"
    if status.credential == "missing":
        return "✗", "Missing credential"
    if status.connection is ConnectionState.FAILED:
        return "✗", "Connection failed"
    if status.connection is ConnectionState.UNSUPPORTED:
        return "✗", "Connection test unsupported"
    return "✓", "Ready"


def _render_dashboard(statuses, out):
    ready = missing = 0
    out.write_line("Guardrail Hub — LLM Setup")
    out.write_line("")
    out.write_line("Providers")
    for item in statuses.values():
        mark, label = _provider_status_label(item)
        if label == "Ready":
            ready += 1
        elif label == "Missing credential":
            missing += 1
        out.write_line("")
        out.write_line(f"{mark} {item.provider.provider_id}")
        out.write_line(f"  Authentication: {_authentication_label(item.provider)}")
        out.write_line(f"  Status: {label}")
    out.write_line("")
    out.write_line("Summary")
    out.write_line(f"  Ready:   {ready}")
    out.write_line(f"  Missing: {missing}")
    out.write_line(f"  Total:   {len(statuses)}")


def _read_selection(reader, out, option_count: int):
    """Return a valid one-based menu selection, or report and retry invalid input."""
    raw = reader(f"Select [1-{option_count}]: ").strip()
    try:
        selection = int(raw)
    except ValueError:
        selection = 0
    if 1 <= selection <= option_count:
        return selection
    labels = [str(index) for index in range(1, option_count + 1)]
    expected = labels[0] if option_count == 1 else " or ".join(labels) if option_count == 2 else ", ".join(labels[:-1]) + f", or {labels[-1]}"
    out.write_line(f"Invalid selection. Please choose {expected}.")
    return None


def _main_menu(session, store, tester, prompt, out, reader, external):
    while True:
        session.show_screen()
        _render_dashboard(session.statuses, out)
        eligibility = {
            status.provider.provider_id: (
                _credential_mutation_eligibility(
                    status, _CredentialMutationAction.CONFIGURE, read_only=external,
                ),
                _credential_mutation_eligibility(
                    status, _CredentialMutationAction.RECONFIGURE, read_only=external,
                ),
            )
            for status in session.statuses.values()
        }
        configurable_missing = [
            status.provider for status in session.statuses.values()
            if eligibility[status.provider.provider_id][0].allowed
        ]
        reconfigurable = [
            status.provider for status in session.statuses.values()
            if eligibility[status.provider.provider_id][1].allowed
        ]
        testable = [s.provider for s in session.statuses.values() if _is_testable(s)]
        viewable = [s.provider for s in session.statuses.values()]
        actions = []
        if reconfigurable:
            actions.append(("Reconfigure configured providers", "configure", reconfigurable, True))
        if configurable_missing:
            actions.append(("Add credentials for missing providers", "configure", configurable_missing, False))
        if testable:
            actions.append(("Test provider connections", "test", testable, None))
        if viewable:
            actions.append(("View provider details", "details", viewable, None))
        for status in session.statuses.values():
            if any(
                result.blocker is _CredentialMutationBlocker.READ_ONLY
                for result in eligibility[status.provider.provider_id]
            ):
                out.write_line("")
                _render_external_credential_guidance(status.provider.provider_id, out, external)
        actions.append(("Exit", "exit", None, None))
        out.write_line("")
        out.write_line("What would you like to do?")
        out.write_line("")
        for index, (label, _, _, _) in enumerate(actions, 1):
            out.write_line(f"{index}. {label}")
        while True:
            choice = _read_selection(reader, out, len(actions))
            if choice is not None:
                break
        _label, action, providers, reconfigure = actions[choice - 1]
        if action == "exit":
            return
        if action == "configure":
            _select_and_configure(providers, bool(reconfigure), session, store, tester, prompt, out, reader)
        elif action == "test":
            _select_and_test(providers, session, store, tester, out, reader)
        else:
            _select_and_view(providers, session, store, tester, prompt, out, reader, external)


def _select_and_configure(providers, reconfigure, session, store, tester, prompt, out, reader):
    """Present the credential target screen, then enter the shared credential flow."""
    title = "Guardrail Hub — Reconfigure Credential" if reconfigure else "Guardrail Hub — Configure Credential"
    heading = "Configured providers" if reconfigure else "Providers missing credentials"
    action = _CredentialMutationAction.RECONFIGURE if reconfigure else _CredentialMutationAction.CONFIGURE
    while True:
        eligible = [
            item for item in providers
            if _credential_mutation_eligibility(
                session.statuses[item.provider_id], action, read_only=False,
            ).allowed
        ]
        if not eligible:
            return "dashboard"
        selected = _select_provider(eligible, heading, session, out, reader, title=title)
        if selected is None:
            return
        outcome = _credential_flow(
            selected, reconfigure, providers, session, store, tester, prompt, out, reader,
        )
        if outcome == "dashboard":
            return


def _select_and_test(providers, session, store, tester, out, reader):
    selected = _select_provider(
        providers, "Providers available for connection testing", session, out, reader,
        title="Guardrail Hub — Test Connection",
    )
    if selected is not None:
        _test_flow(selected, providers, session, store, tester, out, reader)


def _select_and_view(providers, session, store, tester, prompt, out, reader, external):
    while True:
        selected = _select_provider(providers, "Provider Details Selection", session, out, reader)
        if selected is None:
            return
        outcome = _provider_details_screen(
            selected, session, store, tester, prompt, out, reader, external, parent="selection",
        )
        if outcome == "dashboard":
            return


def _select_provider(providers, heading, session, out, reader, *, title=None):
    # The list is rendered once on entry. Invalid input deliberately remains
    # inline so it does not clear the current screen or rescan providers.
    session.show_screen()
    if title is not None:
        out.write_line(title)
        out.write_line("")
    out.write_line(heading)
    out.write_line("")
    for index, provider in enumerate(providers, 1): out.write_line(f"{index}. {provider.provider_id}")
    out.write_line(f"{len(providers) + 1}. Back")
    while True:
        selected = _read_selection(reader, out, len(providers) + 1)
        if selected is None:
            continue
        return None if selected == len(providers) + 1 else providers[selected - 1]


def _provider_details_screen(provider, session, store, tester, prompt, out, reader, external, *, parent):
    while True:
        session.show_screen()
        status = session.statuses[provider.provider_id]
        out.write_line("Provider Details")
        out.write_line("")
        _render_provider_details(status, out)
        options = []
        configure = _credential_mutation_eligibility(
            status, _CredentialMutationAction.CONFIGURE, read_only=external,
        )
        reconfigure = _credential_mutation_eligibility(
            status, _CredentialMutationAction.RECONFIGURE, read_only=external,
        )
        if configure.allowed:
            options.append(("Configure credential", "configure_credential"))
        elif reconfigure.allowed:
            options.append(("Reconfigure credential", "reconfigure_credential"))
        read_only = next(
            (result for result in (configure, reconfigure) if result.blocker is _CredentialMutationBlocker.READ_ONLY),
            None,
        )
        if read_only is not None:
            _render_external_credential_guidance(provider.provider_id, out, external)
            out.write_line("")
        if _is_testable(status): options.append(("Test connection", "test"))
        options.append(("Back to provider details selection" if parent == "selection" else "Back to main menu", "back"))
        for index, (label, _) in enumerate(options, 1): out.write_line(f"{index}. {label}")
        while True:
            selected = _read_selection(reader, out, len(options))
            if selected is not None:
                break
        action = options[selected - 1][1]
        if action == "back": return "dashboard" if parent == "dashboard" else "selection"
        if action == "test":
            testable = [item.provider for item in session.statuses.values() if _is_testable(item)]
            _test_flow(provider, testable, session, store, tester, out, reader)
            return "dashboard"
        outcome = _credential_flow(
            provider, action == "reconfigure_credential", [provider], session, store, tester, prompt, out, reader,
        )
        if outcome == "dashboard":
            return "dashboard"


def _render_provider_details(status: ProviderStatus, out: OutputWriter) -> None:
    out.write_line(status.provider.provider_id)
    out.write_line("")
    out.write_line(f"Enabled: {'Yes' if status.provider.enabled else 'No'}")
    out.write_line(f"Authentication: {_authentication_label(status.provider)}")
    out.write_line(f"Credential: {_credential_label(status.credential)}")
    out.write_line(f"Connection: {_connection_label(status.connection)}")
    out.write_line(f"Deployment: {status.provider.deployment.value.replace('_', ' ').title()}")
    out.write_line("")


def _is_testable(status: ProviderStatus) -> bool:
    return status.provider.enabled and status.credential not in {"missing"}


def _credential_label(credential: str) -> str:
    return {
        "not_required": "Not required",
        "missing": "Missing",
        "aws_detected": "Available",
        "configured": "Configured",
        "externally_managed": "Configured",
    }.get(credential, "Unknown")


def _connection_label(connection: ConnectionState) -> str:
    return {
        ConnectionState.NOT_TESTED: "Not tested",
        ConnectionState.READY: "Ready",
        ConnectionState.FAILED: "Failed",
        ConnectionState.UNSUPPORTED: "Unsupported",
    }[connection]


def _credential_flow(
    provider, reconfigure, providers, session, store, tester, prompt, out, reader, *, read_only=False,
):
    """Run credential entry/result screens without exposing candidate secrets."""
    status = session.statuses[provider.provider_id]
    action = _CredentialMutationAction.RECONFIGURE if reconfigure else _CredentialMutationAction.CONFIGURE
    eligibility = _credential_mutation_eligibility(status, action, read_only=read_only)
    if not eligibility.allowed:
        return _credential_unavailable_screen(
            provider, eligibility, session, store, tester, prompt, out, reader, read_only,
        )
    candidate = None
    entered = None
    stored = False
    message = ""
    try:
        while True:
            if not stored and candidate is None:
                session.show_screen()
                out.write_line("Guardrail Hub — Reconfigure Credential" if reconfigure else "Guardrail Hub — Configure Credential")
                out.write_line("")
                out.write_line(provider.provider_id)
                out.write_line("")
                out.write_line(f"Authentication: {_authentication_label(provider)}")
                out.write_line(f"Credential: {_credential_label(status.credential)}" if reconfigure else "Status: Missing credential")
                out.write_line("")
                if reconfigure and status.credential == "configured":
                    out.write_line("Your existing credential will be preserved unless the new credential is valid.")
                    out.write_line("")
                while candidate is None:
                    entered = prompt.read_secret("Enter new API key:\n> " if reconfigure else "Enter API key:\n> ")
                    if entered and entered.strip():
                        candidate = entered
                        entered = None
                        out.write_line("Credential received. Testing connection...")
                    else:
                        out.write_line("No credential entered. Please try again.")

            if not stored:
                active_tester = tester or _default_tester(provider)
                result = active_tester.test(provider, candidate_credential=candidate)
                session.statuses[provider.provider_id] = ProviderStatus(provider, status.credential, result.state)
                if result.state is ConnectionState.READY:
                    try:
                        store.set(provider.provider_id, candidate)
                    except CredentialBackendError as exc:
                        candidate = None
                        return _credential_result_screen(
                            provider, reconfigure, providers,
                            f"Credential storage failed: {exc.operator_reason}",
                            False, session, store, tester, out, reader, retryable=False,
                        )
                    except LLMConfigurationError as exc:
                        candidate = None
                        return _credential_result_screen(
                            provider, reconfigure, providers, f"Credential storage failed: {type(exc).__name__}",
                            False, session, store, tester, out, reader, retryable=False,
                        )
                    candidate = None
                    stored = True
                    session.changed = True
                    session.statuses[provider.provider_id] = ProviderStatus(provider, "configured", ConnectionState.READY)
                    message = "✓ Credential valid\n✓ Connection successful\n" + ("✓ Credential updated securely" if reconfigure else "✓ Credential stored securely")
                else:
                    message = "✗ Connection failed\n" + ("Existing credential was not changed." if reconfigure else "Credential was not stored.")

            action = _credential_result_screen(
                provider, reconfigure, providers, message, stored, session, store, tester, out, reader,
            )
            if action == "test_again":
                if stored:
                    _result, connection_message = _test_existing(provider, session, store, tester)
                    message = "✓ Credential valid\n" + connection_message + "\n" + ("✓ Credential updated securely" if reconfigure else "✓ Credential stored securely")
                continue
            if action == "new_candidate":
                candidate = None
                stored = False
                continue
            return action
    finally:
        candidate = None
        entered = None


def _credential_result_screen(provider, reconfigure, providers, message, succeeded, session, store, tester, out, reader, *, retryable=True):
    while True:
        session.show_screen()
        out.write_line("Guardrail Hub — Reconfigure Credential" if reconfigure else "Guardrail Hub — Configure Credential")
        out.write_line("")
        out.write_line(provider.provider_id)
        out.write_line("")
        for line in message.splitlines(): out.write_line(line)
        out.write_line("")
        if succeeded:
            options = [("Test again", "test_again")]
        elif retryable:
            options = [("Enter another API key", "new_candidate"), ("Test again", "test_again")]
        else:
            options = []
        action = _CredentialMutationAction.RECONFIGURE if reconfigure else _CredentialMutationAction.CONFIGURE
        alternate = [
            item for item in providers
            if item.provider_id != provider.provider_id
            and _credential_mutation_eligibility(
                session.statuses[item.provider_id], action, read_only=False,
            ).allowed
        ]
        if alternate:
            options.append(("Reconfigure another provider" if reconfigure else "Configure another missing provider", "selection"))
        options.append(("Back to main menu", "dashboard"))
        for index, (label, _action) in enumerate(options, 1): out.write_line(f"{index}. {label}")
        while True:
            choice = _read_selection(reader, out, len(options))
            if choice is not None:
                break
        return options[choice - 1][1]


def _credential_mutation_eligibility(
    status: ProviderStatus,
    action: _CredentialMutationAction,
    *,
    read_only: bool,
) -> _CredentialMutationEligibility:
    """Return the configure/reconfigure decision shared by every setup entry path."""
    if not status.provider.enabled:
        return _CredentialMutationEligibility(action, _CredentialMutationBlocker.DISABLED)
    if status.provider.auth.type is AuthType.AWS:
        return _CredentialMutationEligibility(action, _CredentialMutationBlocker.AWS_AUTH)
    if status.provider.auth.type is not AuthType.API_KEY:
        return _CredentialMutationEligibility(action, _CredentialMutationBlocker.NO_AUTH)
    configured = status.credential in {"configured", "externally_managed"}
    if read_only:
        return _CredentialMutationEligibility(action, _CredentialMutationBlocker.READ_ONLY)
    if action is _CredentialMutationAction.CONFIGURE and status.credential != "missing":
        blocker = (
            _CredentialMutationBlocker.ALREADY_CONFIGURED
            if configured else _CredentialMutationBlocker.UNAVAILABLE_STATE
        )
        return _CredentialMutationEligibility(action, blocker)
    if action is _CredentialMutationAction.RECONFIGURE and not configured:
        blocker = (
            _CredentialMutationBlocker.MISSING
            if status.credential == "missing" else _CredentialMutationBlocker.UNAVAILABLE_STATE
        )
        return _CredentialMutationEligibility(action, blocker)
    return _CredentialMutationEligibility(action)


def _credential_unavailable_screen(
    provider, eligibility, session, store, tester, prompt, out, reader, read_only,
):
    """Explain why a shortcut cannot mutate, then retain read-only navigation."""
    status = session.statuses[provider.provider_id]
    session.show_screen()
    title = (
        "Guardrail Hub — Credential Required"
        if eligibility.action is _CredentialMutationAction.CONFIGURE
        and eligibility.blocker is _CredentialMutationBlocker.READ_ONLY
        else "Guardrail Hub — Credential Changes Unavailable"
    )
    out.write_line(title)
    out.write_line("")
    out.write_line(provider.provider_id)
    out.write_line("")
    out.write_line(f"Authentication: {_authentication_label(provider)}")
    out.write_line(f"Credential: {_credential_label(status.credential)}")
    out.write_line("")
    _render_credential_mutation_blocker(status, eligibility, out, read_only)
    out.write_line("")
    out.write_line("What would you like to do?")
    out.write_line("")
    out.write_line("1. View provider details")
    out.write_line("2. Back to main menu")
    while True:
        choice = _read_selection(reader, out, 2)
        if choice is not None:
            break
    if choice == 1:
        return _provider_details_screen(
            provider, session, store, tester, prompt, out, reader, read_only, parent="dashboard",
        )
    return "dashboard"


def _test_flow(provider, providers, session, store, tester, out, reader):
    """Keep connection testing in one provider-scoped selection/result flow."""
    while True:
        result, message = _test_existing(provider, session, store, tester)
        session.show_screen()
        out.write_line("Guardrail Hub — Test Connection")
        out.write_line("")
        out.write_line(provider.provider_id)
        out.write_line("")
        out.write_line(message)
        out.write_line("")
        options = [
            ("Test again", "again"),
            ("Test another provider", "another"),
            ("Back to main menu", "dashboard"),
        ]
        for index, (label, _action) in enumerate(options, 1): out.write_line(f"{index}. {label}")
        while True:
            choice = _read_selection(reader, out, len(options))
            if choice is not None:
                break
        action = options[choice - 1][1]
        if action == "again":
            continue
        if action == "another":
            selected = _select_provider(
                providers, "Providers available for connection testing", session, out, reader,
                title="Guardrail Hub — Test Connection",
            )
            if selected is None:
                return "dashboard"
            provider = selected
            continue
        return "dashboard"


def _test_existing(provider, session, store, tester):
    credential = None
    if provider.auth.type is AuthType.API_KEY:
        try: credential = store.get(provider.provider_id)
        except CredentialNotFoundError:
            return None, "✗ Connection failed\nMissing credential."
    active_tester = tester or _default_tester(provider)
    result = active_tester.test(provider, candidate_credential=credential)
    session.statuses[provider.provider_id] = ProviderStatus(provider, session.statuses[provider.provider_id].credential, result.state)
    if result.state is ConnectionState.READY:
        return result, "✓ Connection successful"
    return result, "✗ Connection failed"


def _unknown_provider(provider_id, out):
    out.write_line(f"Provider '{provider_id}' is not configured."); out.write_line(""); out.write_line("To add or change providers:"); out.write_line(""); out.write_line("  guardrail-hub config apply <llm.yaml>")


def _render_credential_mutation_blocker(
    status: ProviderStatus,
    eligibility: _CredentialMutationEligibility,
    out: OutputWriter,
    read_only_context: _ReadOnlyCredentialContext | bool = False,
) -> None:
    """Render state-aware guidance for a denied credential mutation."""
    blocker = eligibility.blocker
    if blocker is _CredentialMutationBlocker.READ_ONLY:
        _render_external_credential_guidance(
            status.provider.provider_id, out, read_only_context,
        )
    elif blocker is _CredentialMutationBlocker.DISABLED:
        out.write_line("Credential configuration is unavailable because this provider is disabled.")
    elif blocker is _CredentialMutationBlocker.NO_AUTH:
        out.write_line("This provider does not require an API key. Credential configuration is unavailable.")
    elif blocker is _CredentialMutationBlocker.AWS_AUTH:
        out.write_line("This provider uses the AWS SDK credential chain. API-key credential configuration is unavailable.")
    elif blocker is _CredentialMutationBlocker.ALREADY_CONFIGURED:
        out.write_line("This provider's credential is already configured.")
        out.write_line(
            f"Use guardrail-hub setup --provider {status.provider.provider_id} --reconfigure to replace it."
        )
    elif blocker is _CredentialMutationBlocker.MISSING:
        out.write_line("This provider's credential is missing.")
        out.write_line(
            f"Use guardrail-hub setup --provider {status.provider.provider_id} --credential to configure it."
        )
    elif blocker is _CredentialMutationBlocker.UNAVAILABLE_STATE:
        out.write_line("Credential configuration is unavailable for this provider's current credential state.")


def _render_external_credential_guidance(
    provider_id: str,
    out: OutputWriter,
    read_only_context: _ReadOnlyCredentialContext | bool = True,
) -> None:
    """Explain the supported host provisioning path for a read-only runtime."""
    if read_only_context is _ReadOnlyCredentialContext.ENVIRONMENT:
        out.write_line("Credential changes are unavailable in this read-only runtime context.")
        out.write_line("Credentials for this provider are supplied by the deployment environment.")
        out.write_line("Update them through the deployment system that launches Guardrail Hub.")
        return

    out.write_line("Credential changes are unavailable inside the running MCP container.")
    out.write_line("This is a read-only runtime context; provider credentials can only be changed from the host.")
    out.write_line("")
    out.write_line("For the Guardrail Hub Docker Compose deployment, configure this provider from the host:")
    out.write_line("")
    out.write_line("  cd mcp-server")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", provider_id):
        out.write_line(f"  uv run guardrail-hub setup --provider {provider_id}")
    else:
        out.write_line("  The provider ID cannot be rendered safely in a shell command.")
        out.write_line("  Open Provider Details from this project and select the provider there.")
    out.write_line("")
    out.write_line("Then choose:")
    out.write_line("  Docker Compose credential provisioning")
    out.write_line("")
    out.write_line("For other deployment platforms, update the provider through that platform's secret manager.")


if __name__ == "__main__": sys.exit(main())
