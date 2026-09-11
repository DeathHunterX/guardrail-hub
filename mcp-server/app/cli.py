"""Operator CLI for configured LLM providers and llm.yaml topology."""
from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import tempfile
import threading
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Sequence, TextIO

from app.intelligence.credentials import (
    CredentialBackendError,
    CredentialNotFoundError,
    CredentialStore,
)
from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.registry.builders.catalog_builder import CatalogBuilder
from app.intelligence.registry.exceptions import RegistryLoadError, RegistryValidationError
from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoadResult, LLmConfigLoader
from app.intelligence.registry.models.provider import AuthType, ProviderRecord
from app.intelligence.setup.connection import ConnectionState, ProviderConnectionTester
from app.intelligence.setup.ports import AwsCredentialDetector, OutputWriter, SecretPrompt

_EXIT_OK, _EXIT_CONFIG_ERROR, _EXIT_SETUP_ERROR = 0, 2, 3
_PROG = "guardrail-hub"


class _ConnectionSpinner:
    """Presentation-only fixed-line activity indicator for a blocking probe."""

    _BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    _ASCII_FRAMES = ("|", "/", "-", "\\")

    def __init__(self, output: OutputWriter, *, interval: float = 0.1) -> None:
        self._output = output
        self._interval = interval
        self._stop_requested = threading.Event()
        self._worker: threading.Thread | None = None
        self._frames = self._select_frames()
        self._frame_index = 0
        self._line_width = max(len(f"{frame} Testing connection...") for frame in self._frames)

    def __enter__(self) -> "_ConnectionSpinner":
        # The first frame is intentionally synchronous: the probe must never
        # start before the operator has seen an explicitly flushed activity cue.
        self._write_frame()
        self._worker = threading.Thread(
            target=self._animate,
            name="guardrail-connection-spinner",
            daemon=False,
        )
        self._worker.start()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> bool:
        self.stop()
        return False

    def stop(self) -> None:
        """Stop, join, and erase the active line before any screen transition."""
        self._stop_requested.set()
        if self._worker is not None:
            self._worker.join()
            self._worker = None
        self._output.write("\r" + (" " * self._line_width) + "\r")
        self._output.flush()

    def _animate(self) -> None:
        while not self._stop_requested.wait(self._interval):
            self._write_frame()

    def _write_frame(self) -> None:
        frame = self._frames[self._frame_index]
        self._frame_index = (self._frame_index + 1) % len(self._frames)
        self._output.write(f"\r{frame} Testing connection...")
        self._output.flush()

    def _select_frames(self) -> tuple[str, ...]:
        encoding = getattr(self._output, "encoding", None)
        if encoding:
            try:
                "".join(self._BRAILLE_FRAMES).encode(encoding)
            except (LookupError, UnicodeError):
                return self._ASCII_FRAMES
        return self._BRAILLE_FRAMES


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


def _enable_windows_vt(output: TextIO) -> tuple[bool, Callable[[], None] | None]:
    """Return native-console detection plus a restorer when VT is usable."""
    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(output.fileno())
        original_mode = ctypes.c_uint()
        kernel32 = ctypes.windll.kernel32
        if not kernel32.GetConsoleMode(handle, ctypes.byref(original_mode)):
            return False, None
        enabled_mode = original_mode.value | 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        changed = enabled_mode != original_mode.value
        if changed and not kernel32.SetConsoleMode(handle, enabled_mode):
            return True, None
    except (AttributeError, OSError, ValueError):
        return False, None

    def restore() -> None:
        if changed:
            kernel32.SetConsoleMode(handle, original_mode.value)

    return True, restore


class _AlternateScreen:
    """Temporarily isolate interactive setup output from the calling shell."""

    _ENTER = "\x1b[?1049h\x1b[H\x1b[?25h"
    _LEAVE = "\x1b[?25h\x1b[?1049l"
    _REDRAW = "\x1b[2J\x1b[H"

    def __init__(self, output: TextIO, input_stream: TextIO, *, term: str | None = None) -> None:
        self._output = output
        self._interactive = self._streams_are_interactive(input_stream, output)
        self._term = (term if term is not None else os.environ.get("TERM", "")).lower()
        self._windows = os.name == "nt"
        self._active = self._interactive and not self._windows and self._term != "dumb"
        self._entered = False
        self._restore_windows_vt: Callable[[], None] | None = None

    @staticmethod
    def _streams_are_interactive(input_stream: TextIO, output: TextIO) -> bool:
        try:
            return input_stream.isatty() and output.isatty()
        except (AttributeError, OSError):
            return False

    def __enter__(self) -> "_AlternateScreen":
        if self._interactive and self._windows:
            native_console, self._restore_windows_vt = _enable_windows_vt(self._output)
            self._active = self._restore_windows_vt is not None
            if not native_console and self._term != "dumb":
                self._active = bool(
                    self._term
                    or os.environ.get("WT_SESSION")
                    or os.environ.get("ConEmuANSI")
                )
        if self._active:
            try:
                self._output.write(self._ENTER)
                self._output.flush()
                self._entered = True
            except BaseException:
                self._restore_console_mode()
                self._active = False
                raise
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> bool:
        try:
            if self._entered:
                self._output.write(self._LEAVE)
                self._output.flush()
        finally:
            self._entered = False
            self._active = False
            self._restore_console_mode()
        return False

    def _restore_console_mode(self) -> None:
        restore = self._restore_windows_vt
        self._restore_windows_vt = None
        if restore is not None:
            restore()

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
    credential_state: "_CredentialState | None" = None
    selected_target: "_CredentialTarget | None" = None
    other_target: "_CredentialTarget | None" = None
    other_target_configured: bool = False
    other_target_error: bool = False


class _CredentialState(str, Enum):
    CONFIGURED_HERE = "configured_here"
    CONFIGURED_OTHER_TARGET = "configured_other_target"
    MISSING = "missing"
    BACKEND_ERROR = "backend_error"


class _CredentialTarget(str, Enum):
    WINDOWS_LOCAL = "Windows local credential store"
    COMPOSE_HOST = "Docker Compose provisioning"


@dataclass(frozen=True, slots=True)
class _CredentialTargetContext:
    """Presence-only context for the one other recognized target."""

    selected: _CredentialTarget
    other: _CredentialTarget
    other_backend: object


@dataclass(frozen=True, slots=True)
class _StoreResolution:
    store: CredentialStore | None
    read_only_context: "_ReadOnlyCredentialContext | bool"
    failed: bool
    target_context: _CredentialTargetContext | None = None

    def __iter__(self):
        """Retain the established three-value resolver unpacking contract."""
        yield self.store
        yield self.read_only_context
        yield self.failed


class _CredentialMutationAction(str, Enum):
    CONFIGURE = "configure"
    RECONFIGURE = "reconfigure"


class _ReadOnlyCredentialContext(str, Enum):
    CONTAINER_FILE = "container_file"
    ENVIRONMENT = "environment"


class _SetupScopeKind(str, Enum):
    GLOBAL = "global"
    PROVIDER = "provider"


@dataclass(frozen=True, slots=True)
class _SetupScope:
    kind: _SetupScopeKind
    provider_id: str | None = None

    @classmethod
    def provider(cls, provider_id: str) -> "_SetupScope":
        return cls(_SetupScopeKind.PROVIDER, provider_id)

    def is_provider(self, provider_id: str) -> bool:
        return self.kind is _SetupScopeKind.PROVIDER and self.provider_id == provider_id


_GLOBAL_SETUP_SCOPE = _SetupScope(_SetupScopeKind.GLOBAL)


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
    scope: _SetupScope = _GLOBAL_SETUP_SCOPE
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
    config = commands.add_parser("config", help="Inspect and manage llm.yaml provider/model topology.")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("show", help="Safely show the current LLM configuration.")
    validate = config_commands.add_parser("validate", help="Strictly validate a candidate llm.yaml.")
    validate.add_argument("llm_yaml", metavar="LLM_YAML")
    apply = config_commands.add_parser("apply", help="Interactively validate, diff, and apply a candidate llm.yaml.")
    apply.add_argument("llm_yaml", metavar="LLM_YAML")
    return parser


def main(argv: Optional[Sequence[str]] = None, *, credential_store: Optional[CredentialStore] = None,
         secret_prompt: Optional[SecretPrompt] = None, aws_detector: Optional[AwsCredentialDetector] = None,
         output: Optional[OutputWriter] = None, input_reader: Optional[Callable[[str], str]] = None,
         connection_tester: Optional[ProviderConnectionTester] = None) -> int:
    args = _build_parser().parse_args(argv)
    from app.intelligence.setup.adapters import Boto3AwsCredentialDetector, MaskedSecretPrompt, SecureInputUnavailableError, StreamOutputWriter
    out, prompt, detector, reader = output or StreamOutputWriter(), secret_prompt or MaskedSecretPrompt(), aws_detector or Boto3AwsCredentialDetector(), input_reader or input
    try:
        if args.command == "config":
            return _run_config(args, out, reader)
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
        out.write_line(
            "Setup cancelled."
            if args.command == "setup"
            else "Configuration apply cancelled."
        )
        return _EXIT_OK
    except Exception as exc:  # noqa: BLE001 - setup must restore a usable terminal.
        if args.command == "setup":
            out.write_line(f"Setup error: {type(exc).__name__}")
            return _EXIT_SETUP_ERROR
        raise


def _current_config_path() -> Path:
    """Resolve only this setting, without importing full application Settings."""
    return Path(os.environ.get("REGISTRY_LLM_CONFIG_PATH", "config/llm.yaml"))


def _load_validated(path: Path, *, strict: bool = False, text: str | None = None):
    loader = LLmConfigLoader()
    result = loader.load_text(text, file_path=str(path), strict=strict) if text is not None else loader.load(path, strict=strict)
    if result.errors:
        from app.intelligence.registry.exceptions import LoadIssue, LoadReport
        raise RegistryLoadError(LoadReport(issues=tuple(LoadIssue(file_path=str(path), position="(root)", message=error) for error in result.errors)))
    catalog, _warnings, _errors = CatalogBuilder().build_from_llm_config_result(result)
    return result, catalog


def _run_config(args: argparse.Namespace, out: OutputWriter, reader: Callable[[str], str]) -> int:
    current = _current_config_path()
    try:
        if args.config_command == "show":
            result, _ = _load_validated(current)
            _render_config(result, out)
            return _EXIT_OK
        candidate = Path(args.llm_yaml)
        if args.config_command == "validate":
            _load_validated(candidate, strict=True)
            out.write_line("Configuration is valid.")
            return _EXIT_OK
        return _apply_config(current, candidate, out, reader)
    except (RegistryLoadError, RegistryValidationError) as exc:
        out.write_line("Configuration error:"); out.write_line(str(exc)); return _EXIT_CONFIG_ERROR
    except OSError as exc:
        out.write_line(f"Configuration error: {type(exc).__name__}"); return _EXIT_CONFIG_ERROR


def _render_config(result: LLmConfigLoadResult, out: OutputWriter) -> None:
    by_provider: dict[str, list] = {}
    for model in result.models: by_provider.setdefault(model.provider_id, []).append(model)
    for provider in result.providers:
        auth = provider.auth.type.value if isinstance(provider.auth.type, AuthType) else "not_required"
        out.write_line(f"{provider.provider_id}: type={provider.provider_type.value}, deployment={provider.deployment.value}, enabled={provider.enabled}, auth={auth}, priority={provider.priority}")
        for model in sorted(by_provider.get(provider.provider_id, []), key=lambda item: item.model_id):
            capabilities = ",".join(sorted(cap.value for cap in model.capabilities))
            out.write_line(f"  - {model.model_id} -> {provider.provider_id} ({model.model_type.value}; capabilities={capabilities}; priority={model.priority})")


def _apply_config(current: Path, candidate: Path, out: OutputWriter, reader: Callable[[str], str]) -> int:
    if not sys.stdin.isatty() and reader is input:
        out.write_line("Configuration apply requires an interactive terminal."); return _EXIT_SETUP_ERROR
    candidate_bytes = candidate.read_bytes()
    candidate_result, _ = _load_validated(candidate, strict=True, text=candidate_bytes.decode("utf-8"))
    current_result, _ = _load_validated(current)
    diff = _semantic_diff(current_result, candidate_result)
    if not diff:
        out.write_line("No configuration changes to apply."); return _EXIT_OK
    out.write_line("Configuration changes:")
    for line in diff: out.write_line(f"  {line}")
    try: confirmed = reader("Apply these changes? [y/N]: ").strip().lower()
    except (EOFError, OSError): confirmed = ""
    if confirmed not in {"y", "yes"}:
        out.write_line("Configuration apply cancelled."); return _EXIT_OK
    _atomic_replace(current, candidate_bytes)
    out.write_line("Configuration applied."); return _EXIT_OK


def _semantic_diff(current: LLmConfigLoadResult, candidate: LLmConfigLoadResult) -> list[str]:
    old_p, new_p = {p.provider_id: p for p in current.providers}, {p.provider_id: p for p in candidate.providers}
    old_m, new_m = {m.model_id: m for m in current.models}, {m.model_id: m for m in candidate.models}
    lines = [f"Provider removed: {item}" for item in sorted(old_p.keys() - new_p.keys())]
    lines += [f"Provider added: {item}" for item in sorted(new_p.keys() - old_p.keys())]
    for item in sorted(old_p.keys() & new_p.keys()):
        old, new = old_p[item], new_p[item]
        fields = [field for field in ("provider_type", "deployment", "enabled", "priority") if getattr(old, field) != getattr(new, field)]
        if old.auth != new.auth: fields.append("authentication")
        if old.connection != new.connection: fields.append("connection")
        if fields: lines.append(f"Provider changed: {item} ({', '.join(fields)})")
    lines += [f"Model removed: {item}" for item in sorted(old_m.keys() - new_m.keys())]
    lines += [f"Model added: {item} -> {new_m[item].provider_id}" for item in sorted(new_m.keys() - old_m.keys())]
    lines += [f"Model changed: {item}" for item in sorted(old_m.keys() & new_m.keys()) if old_m[item] != new_m[item]]
    return lines


def _atomic_replace(target: Path, content: bytes) -> None:
    target_stat = os.lstat(target)
    if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode): raise OSError("current llm.yaml is not a regular file")
    descriptor, name = tempfile.mkstemp(prefix=".guardrail-hub-", dir=target.parent); temporary = Path(name)
    try:
        if hasattr(os, "fchmod"): os.fchmod(descriptor, stat.S_IMODE(target_stat.st_mode))
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1; handle.write(content); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, target); temporary = None
        if os.name != "nt":
            directory = os.open(target.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        if descriptor >= 0: os.close(descriptor)
        if temporary is not None: temporary.unlink(missing_ok=True)


def _run_setup(args, out, prompt, detector, reader, injected_store, injected_tester, redraw: Callable[[], None] = lambda: None) -> int:
    current = _current_config_path()
    try: result, _ = _load_validated(current)
    except (RegistryLoadError, RegistryValidationError) as exc:
        out.write_line("Configuration error:"); out.write_line(str(exc)); return _EXIT_CONFIG_ERROR
    provider = None
    scope = _GLOBAL_SETUP_SCOPE
    inspected_providers = result.providers
    if args.provider:
        provider = next((p for p in result.providers if p.provider_id == args.provider), None)
        if provider is None:
            _unknown_provider(args.provider, result.providers, out)
            return _EXIT_SETUP_ERROR
        scope = _SetupScope.provider(provider.provider_id)
        inspected_providers = [provider]
    resolution = _resolve_store(current, out, reader, injected_store)
    store, external, failed = resolution
    if failed: return _EXIT_SETUP_ERROR
    # Adapter imports are intentionally lazy. A dashboard or an unknown-provider
    # error must not import optional SDKs or construct the application runtime.
    tester = injected_tester
    try:
        session = _SetupSession(
            _inspect(
                inspected_providers,
                store,
                detector,
                external,
                target_context=(
                    resolution.target_context
                    if isinstance(resolution, _StoreResolution)
                    else None
                ),
            ),
            scope=scope,
            redraw=redraw,
        )
    except LLMConfigurationError as exc:
        out.write_line(f"Setup error: credential inspection failed ({type(exc).__name__})")
        return _EXIT_SETUP_ERROR
    if provider is not None:
        if args.credential or args.reconfigure:
            outcome = _credential_flow(
                provider, args.reconfigure, [provider], session, store, tester, prompt, out, reader,
                read_only=external,
            )
            if outcome != "exit":
                _provider_details_screen(
                    provider, session, store, tester, prompt, out, reader, external, parent="dashboard",
                )
        else:
            _provider_details_screen(provider, session, store, tester, prompt, out, reader, external, parent="dashboard")
        return _EXIT_OK
    _main_menu(session, store, tester, prompt, out, reader, external)
    return _EXIT_OK


def _resolve_store(current, out, reader, injected):
    if injected is not None: return _StoreResolution(injected, False, False)
    from app.intelligence.credentials.backend_factory import build_credential_backend, build_provider_env_var_names
    from app.intelligence.credentials.container_backend import ContainerFileCredentialBackend
    from app.intelligence.credentials.env_backend import EnvVarCredentialBackend
    from app.intelligence.setup.compose_host import ComposeHostCredentialProvisioner, recognize_compose_host_project
    compose = recognize_compose_host_project(current)
    try:
        if compose and sys.platform != "win32":
            return _StoreResolution(
                CredentialStore(ComposeHostCredentialProvisioner(compose)),
                False,
                False,
            )
        if compose and sys.platform == "win32":
            if not sys.stdin.isatty() and reader is input:
                out.write_line("Setup error: Windows local and Compose host contexts are both possible; run interactively to choose the deployment context.")
                return _StoreResolution(None, False, True)
            from app.intelligence.credentials.windows_backend import (
                WindowsCredentialManagerBackend,
            )

            windows_backend = WindowsCredentialManagerBackend()
            windows_store = CredentialStore(windows_backend)
            compose_backend = ComposeHostCredentialProvisioner(compose)
            compose_store = CredentialStore(compose_backend)
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
                    return _StoreResolution(
                        compose_store,
                        False,
                        False,
                        _CredentialTargetContext(
                            selected=_CredentialTarget.COMPOSE_HOST,
                            other=_CredentialTarget.WINDOWS_LOCAL,
                            other_backend=windows_backend,
                        ),
                    )
                return _StoreResolution(
                    windows_store,
                    False,
                    False,
                    _CredentialTargetContext(
                        selected=_CredentialTarget.WINDOWS_LOCAL,
                        other=_CredentialTarget.COMPOSE_HOST,
                        other_backend=compose_backend,
                    ),
                )
        records, _ = _load_validated(current)
        backend = build_credential_backend(env_var_names=build_provider_env_var_names(records.providers))
        read_only_context: _ReadOnlyCredentialContext | bool = False
        if isinstance(backend, ContainerFileCredentialBackend):
            read_only_context = _ReadOnlyCredentialContext.CONTAINER_FILE
        elif isinstance(backend, EnvVarCredentialBackend):
            read_only_context = _ReadOnlyCredentialContext.ENVIRONMENT
        return _StoreResolution(CredentialStore(backend), read_only_context, False)
    except LLMConfigurationError as exc:
        out.write_line(f"Setup error: {exc}")
        return _StoreResolution(None, False, True)


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


def _inspect(providers, store, detector, external, *, target_context=None):
    statuses = {}
    for provider in providers:
        credential = "not_required"
        credential_state = None
        other_target_configured = False
        other_target_error = False
        if provider.enabled and provider.auth.type is AuthType.AWS: credential = "aws_detected" if detector.is_available() else "missing"
        elif provider.enabled and provider.auth.type is AuthType.API_KEY:
            try:
                value = store.get(provider.provider_id)
                credential = "configured"
                credential_state = _CredentialState.CONFIGURED_HERE
                del value
            except CredentialNotFoundError:
                credential = "missing"
                credential_state = _CredentialState.MISSING
            except CredentialBackendError:
                credential = "backend_error"
                credential_state = _CredentialState.BACKEND_ERROR

            if target_context is not None:
                try:
                    other_target_configured = bool(
                        target_context.other_backend.credential_exists(
                            provider.provider_id
                        )
                    )
                except CredentialBackendError:
                    other_target_error = True
                if credential == "missing" and other_target_configured:
                    credential_state = _CredentialState.CONFIGURED_OTHER_TARGET
                elif credential == "missing" and other_target_error:
                    credential_state = _CredentialState.BACKEND_ERROR
        statuses[provider.provider_id] = ProviderStatus(
            provider,
            credential,
            credential_state=credential_state,
            selected_target=target_context.selected if target_context else None,
            other_target=target_context.other if target_context else None,
            other_target_configured=other_target_configured,
            other_target_error=other_target_error,
        )
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
    if status.credential_state is _CredentialState.BACKEND_ERROR:
        return "!", "Credential inspection unavailable"
    if status.credential_state is _CredentialState.CONFIGURED_OTHER_TARGET:
        return (
            "!",
            f"Credential configured in {status.other_target.value}; "
            f"not configured for {status.selected_target.value}",
        )
    if status.credential == "missing":
        return "✗", "Missing credential"
    if status.connection is ConnectionState.FAILED:
        return "✗", "Connection failed"
    if status.connection is ConnectionState.UNSUPPORTED:
        return "✗", "Connection test unsupported"
    return "✓", "Ready"


def _render_dashboard(statuses, out):
    ready = missing = configured_elsewhere = inspection_errors = 0
    out.write_line("Guardrail Hub — LLM Setup")
    out.write_line("")
    out.write_line("Providers")
    for item in statuses.values():
        mark, label = _provider_status_label(item)
        if label == "Ready":
            ready += 1
        elif item.credential_state is _CredentialState.BACKEND_ERROR:
            inspection_errors += 1
        elif item.credential_state is _CredentialState.CONFIGURED_OTHER_TARGET:
            configured_elsewhere += 1
        elif item.credential == "missing":
            missing += 1
        out.write_line("")
        out.write_line(f"{mark} {item.provider.provider_id}")
        out.write_line(f"  Authentication: {_authentication_label(item.provider)}")
        out.write_line(f"  Status: {label}")
    out.write_line("")
    out.write_line("Summary")
    out.write_line(f"  Ready:   {ready}")
    out.write_line(f"  Missing: {missing}")
    out.write_line(f"  Configured elsewhere: {configured_elsewhere}")
    out.write_line(f"  Inspection errors: {inspection_errors}")
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
        if session.scope.is_provider(provider.provider_id):
            options.append(("Exit", "exit"))
        else:
            options.append(("Back to provider details selection" if parent == "selection" else "Back to main menu", "back"))
        for index, (label, _) in enumerate(options, 1): out.write_line(f"{index}. {label}")
        while True:
            selected = _read_selection(reader, out, len(options))
            if selected is not None:
                break
        action = options[selected - 1][1]
        if action == "exit": return "exit"
        if action == "back": return "dashboard" if parent == "dashboard" else "selection"
        if action == "test":
            testable = [provider] if session.scope.is_provider(provider.provider_id) else [
                item.provider for item in session.statuses.values() if _is_testable(item)
            ]
            outcome = _test_flow(provider, testable, session, store, tester, out, reader)
            if session.scope.is_provider(provider.provider_id):
                if outcome == "exit": return "exit"
                continue
            return "dashboard"
        outcome = _credential_flow(
            provider, action == "reconfigure_credential", [provider], session, store, tester, prompt, out, reader,
        )
        if session.scope.is_provider(provider.provider_id):
            if outcome == "exit": return "exit"
            continue
        if outcome == "dashboard":
            return "dashboard"


def _render_provider_details(status: ProviderStatus, out: OutputWriter) -> None:
    out.write_line(status.provider.provider_id)
    out.write_line("")
    out.write_line(f"Enabled: {'Yes' if status.provider.enabled else 'No'}")
    out.write_line(f"Authentication: {_authentication_label(status.provider)}")
    for line in _credential_status_lines(status):
        out.write_line(line)
    out.write_line(f"Connection: {_connection_label(status.connection)}")
    out.write_line(f"Deployment: {status.provider.deployment.value.replace('_', ' ').title()}")
    out.write_line("")


def _is_testable(status: ProviderStatus) -> bool:
    return status.provider.enabled and status.credential in {
        "configured",
        "externally_managed",
        "not_required",
        "aws_detected",
    }


def _credential_status_lines(status: ProviderStatus) -> tuple[str, ...]:
    """Render target-aware credential state without backend error details."""
    selected = status.selected_target
    other = status.other_target
    if selected is None or status.credential_state is None:
        return (f"Credential: {_credential_label(status.credential)}",)
    if status.credential_state is _CredentialState.CONFIGURED_OTHER_TARGET:
        return (
            f"Credential: Configured in {other.value}",
            f"This credential is not configured for {selected.value}.",
        )
    if status.credential_state is _CredentialState.BACKEND_ERROR:
        lines = ["Credential: Inspection unavailable"]
        if status.credential == "backend_error":
            lines.append(f"{selected.value} could not be inspected.")
        elif status.other_target_error:
            lines.append(f"This credential is not configured for {selected.value}.")
            lines.append(f"{other.value} could not be inspected.")
        return tuple(lines)
    if status.credential_state is _CredentialState.CONFIGURED_HERE:
        lines = [f"Credential: Configured in {selected.value}"]
        if status.other_target_configured:
            lines.append(f"Also configured in {other.value}.")
        elif status.other_target_error:
            lines.append(f"{other.value} could not be inspected.")
        return tuple(lines)
    return (f"Credential: Missing for {selected.value}",)


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
                session.statuses[provider.provider_id] = replace(
                    status, connection=result.state,
                )
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
                    session.statuses[provider.provider_id] = replace(
                        status,
                        credential="configured",
                        connection=ConnectionState.READY,
                        credential_state=_CredentialState.CONFIGURED_HERE,
                    )
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
        if session.scope.is_provider(provider.provider_id):
            options.extend((("Back to provider", "provider"), ("Exit", "exit")))
        else:
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
    out.write_line("2. Exit" if session.scope.is_provider(provider.provider_id) else "2. Back to main menu")
    while True:
        choice = _read_selection(reader, out, 2)
        if choice is not None:
            break
    if choice == 1:
        return _provider_details_screen(
            provider, session, store, tester, prompt, out, reader, read_only, parent="dashboard",
        )
    return "exit" if session.scope.is_provider(provider.provider_id) else "dashboard"


def _test_flow(provider, providers, session, store, tester, out, reader):
    """Keep connection testing in one provider-scoped selection/result flow."""
    while True:
        _render_connection_waiting(provider, session, out)
        with _ConnectionSpinner(out):
            result, message = _test_existing(provider, session, store, tester)
        if result is not None:
            _discard_pending_terminal_input()
        session.show_screen()
        out.write_line("Guardrail Hub — Test Connection")
        out.write_line("")
        out.write_line(provider.provider_id)
        out.write_line("")
        out.write_line(message)
        out.write_line("")
        options = (
            [("Test again", "again"), ("Back to provider", "provider"), ("Exit", "exit")]
            if session.scope.is_provider(provider.provider_id)
            else [
                ("Test again", "again"),
                ("Test another provider", "another"),
                ("Back to main menu", "dashboard"),
            ]
        )
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
        return action


def _render_connection_waiting(provider, session, out) -> None:
    """Replace the current screen before the synchronous connection probe starts."""
    session.show_screen()
    out.write_line("Guardrail Hub — Test Connection")
    out.write_line("")
    out.write_line(provider.provider_id)
    out.write_line("")
    # This explicit boundary matters even though StreamOutputWriter flushes
    # individual lines: a waiting screen is not ready until its full header is
    # visible before the blocking provider call begins.
    out.flush()


def _discard_pending_terminal_input() -> None:
    """Drop only keystrokes queued while a synchronous probe held the result menu closed."""
    try:
        if not sys.stdin.isatty():
            return
    except (AttributeError, OSError):
        return

    if os.name == "nt":
        try:
            import msvcrt
            while msvcrt.kbhit():
                character = msvcrt.getwch()
                if character in ("\x00", "\xe0") and msvcrt.kbhit():
                    msvcrt.getwch()
        except OSError:
            return
        return

    try:
        import termios
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (ImportError, OSError, AttributeError):
        return


def _test_existing(provider, session, store, tester):
    credential = None
    if provider.auth.type is AuthType.API_KEY:
        try: credential = store.get(provider.provider_id)
        except CredentialNotFoundError:
            return None, "✗ Connection failed\nMissing credential."
    active_tester = tester or _default_tester(provider)
    result = active_tester.test(provider, candidate_credential=credential)
    session.statuses[provider.provider_id] = replace(
        session.statuses[provider.provider_id], connection=result.state,
    )
    if result.state is ConnectionState.READY:
        return result, "✓ Connection successful"
    return result, "✗ Connection failed"


def _unknown_provider(provider_id, providers, out):
    out.write_line(f"GuardrailHub: unknown provider '{provider_id}'.")
    out.write_line("")
    out.write_line("Available providers:")
    for provider in sorted(providers, key=lambda item: item.provider_id):
        out.write_line(f"- {provider.provider_id}")
    out.write_line("")
    out.write_line("To add or modify provider configuration:")
    out.write_line("  guardrail-hub config apply <llm.yaml>")


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
