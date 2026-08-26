"""Command-line entrypoint for Guardrail Hub.

This module is the composition root for the ``guardrail-hub`` command. Like
``app/main.py`` (the HTTP entrypoint) and ``app/bootstrap.py`` (the platform
composition root), it lives at the top level of the ``app`` package and is
allowed to wire concrete implementations together — it is not an R1 layering
role.

Currently it exposes a single subcommand, ``setup``, which bootstraps local LLM
credentials from ``config/llm.yaml``:

    guardrail-hub setup
    guardrail-hub setup --config path/to/llm.yaml
    guardrail-hub setup --reconfigure openai-cloud

``main`` is written to be fully testable: the credential store, secret prompt,
AWS detector, and output sink can all be injected, so tests never touch the OS
keyring, a real terminal, or the AWS SDK. Production callers inject nothing and
get the real adapters.

Exit codes:
    0  success — every configured provider is satisfied
    1  incomplete — a required credential is still missing (e.g. no key entered,
       AWS credential chain did not resolve)
    2  configuration error — llm.yaml is missing, malformed, or invalid
    3  setup error — the credential backend or AWS tooling is unavailable
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from app.intelligence.credentials import CredentialStore
from app.intelligence.exceptions.llm import LLMConfigurationError
from app.intelligence.registry.exceptions import RegistryLoadError
from app.intelligence.registry.loaders.llm_config_loader import LLmConfigLoader
from app.intelligence.setup.ports import (
    AwsCredentialDetector,
    OutputWriter,
    SecretPrompt,
)

# ------------------------------------------------------------------
# Exit codes
# ------------------------------------------------------------------

_EXIT_OK = 0
_EXIT_INCOMPLETE = 1
_EXIT_CONFIG_ERROR = 2
_EXIT_SETUP_ERROR = 3

_DEFAULT_CONFIG_PATH = "config/llm.yaml"
_PROG = "guardrail-hub"


# ------------------------------------------------------------------
# Argument parsing
# ------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``guardrail-hub`` command."""
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description="Guardrail Hub command-line utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup",
        help="Configure local LLM provider credentials from config/llm.yaml.",
        description=(
            "Read config/llm.yaml, determine which providers require "
            "credentials, and securely store any that are missing. Does not "
            "modify llm.yaml and does not create a .env file."
        ),
    )
    setup_parser.add_argument(
        "--config",
        default=_DEFAULT_CONFIG_PATH,
        metavar="PATH",
        help=(
            f"Path to the LLM configuration file "
            f"(default: {_DEFAULT_CONFIG_PATH})."
        ),
    )
    setup_parser.add_argument(
        "--reconfigure",
        action="append",
        default=[],
        metavar="PROVIDER_ID",
        help=(
            "Re-prompt for and replace the stored credential of the given "
            "provider even if one already exists. May be repeated."
        ),
    )
    return parser


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    credential_store: Optional[CredentialStore] = None,
    secret_prompt: Optional[SecretPrompt] = None,
    aws_detector: Optional[AwsCredentialDetector] = None,
    output: Optional[OutputWriter] = None,
) -> int:
    """Run the ``guardrail-hub`` command.

    Args:
        argv: Argument vector (excluding the program name). Defaults to
            ``sys.argv[1:]``.
        credential_store: Injected credential store. When None, a default
            persistent secure backend is built for the host platform.
        secret_prompt: Injected hidden-input port. When None, uses getpass.
        aws_detector: Injected AWS credential detector. When None, uses boto3.
        output: Injected user-facing output sink. When None, writes to stdout.

    Returns:
        A process exit code (see module docstring).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "setup":
        return _run_setup(
            args,
            credential_store=credential_store,
            secret_prompt=secret_prompt,
            aws_detector=aws_detector,
            output=output,
        )

    # Unreachable: argparse enforces a valid subcommand (required=True).
    parser.error(f"unknown command: {args.command}")
    return _EXIT_CONFIG_ERROR  # pragma: no cover


def _run_setup(
    args: argparse.Namespace,
    *,
    credential_store: Optional[CredentialStore],
    secret_prompt: Optional[SecretPrompt],
    aws_detector: Optional[AwsCredentialDetector],
    output: Optional[OutputWriter],
) -> int:
    """Execute the ``setup`` subcommand and return its exit code."""
    # Local imports keep the module import cheap and avoid importing adapter
    # dependencies (getpass, boto3, native keyring) unless setup actually runs.
    from app.intelligence.credentials.backend_factory import (
        build_default_credential_backend,
    )
    from app.intelligence.setup.adapters import (
        Boto3AwsCredentialDetector,
        GetpassSecretPrompt,
        StreamOutputWriter,
    )
    from app.intelligence.setup.service import CredentialSetupService

    out: OutputWriter = output if output is not None else StreamOutputWriter()

    # 1. Load configuration. A RegistryLoadError means the file is missing,
    #    unreadable, malformed, or has unresolved env references.
    loader = LLmConfigLoader()
    try:
        result = loader.load(args.config)
    except RegistryLoadError as exc:
        out.write_line("Configuration error: unable to load LLM configuration.")
        # exc carries a structured, secret-free LoadReport.
        out.write_line(str(exc))
        return _EXIT_CONFIG_ERROR

    # 2. Structural validation errors are returned, not raised.
    if result.errors:
        out.write_line(
            f"Configuration error: llm.yaml is invalid "
            f"({len(result.errors)} issue(s)):"
        )
        for error in result.errors:
            out.write_line(f"  - {error}")
        return _EXIT_CONFIG_ERROR

    # 3. Build the credential store. When not injected, select a persistent
    #    secure backend for this platform (fail-closed if none exists).
    if credential_store is not None:
        store = credential_store
    else:
        try:
            store = CredentialStore(build_default_credential_backend())
        except LLMConfigurationError as exc:
            # CredentialBackendError (a LLMConfigurationError) — no secure
            # backend for this platform. Message contains no secret.
            out.write_line(f"Setup error: {exc}")
            return _EXIT_SETUP_ERROR

    # 4. Build the remaining collaborators (injected or real adapters).
    prompt: SecretPrompt = (
        secret_prompt if secret_prompt is not None else GetpassSecretPrompt()
    )
    detector: AwsCredentialDetector = (
        aws_detector if aws_detector is not None else Boto3AwsCredentialDetector()
    )

    # 5. Run the workflow. A LLMConfigurationError here means the backend or the
    #    AWS tooling failed; its message is guaranteed secret-free by design.
    service = CredentialSetupService(
        credential_store=store,
        secret_prompt=prompt,
        aws_detector=detector,
        output=out,
        reconfigure=frozenset(args.reconfigure),
    )
    try:
        report = service.run(result.providers)
    except LLMConfigurationError as exc:
        out.write_line(f"Setup error: {exc}")
        return _EXIT_SETUP_ERROR

    return _EXIT_OK if report.ok else _EXIT_INCOMPLETE


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
