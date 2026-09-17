from __future__ import annotations

import ctypes
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.cli import (
    ProviderStatus,
    _CredentialMutationAction,
    _CredentialState,
    _CredentialTarget,
    _CredentialTargetContext,
    _credential_mutation_eligibility,
    _inspect,
    _render_dashboard,
    _render_provider_details,
    _resolve_store,
)
from app.intelligence.credentials import (
    CredentialBackendError,
    CredentialStore,
    InMemoryCredentialBackend,
)
from app.intelligence.credentials.windows_backend import (
    CRED_TYPE_GENERIC,
    WindowsCredentialManagerBackend,
    _CREDENTIAL,
)
from app.intelligence.registry.models.provider import (
    AuthConfig,
    AuthType,
    Capability,
    ConnectionConfig,
    DeploymentType,
    ProviderRecord,
    ProviderType,
)
from app.intelligence.setup.compose_host import (
    ComposeHostCredentialProvisioner,
    ComposeHostProject,
)


_SECRET = "synthetic-target-state-secret-never-rendered"


class _Output:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write_line(self, text: str) -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class _Detector:
    def is_available(self) -> bool:
        return False


class _MetadataBackend(InMemoryCredentialBackend):
    def __init__(self, *, configured: bool = False, fail: bool = False) -> None:
        super().__init__()
        self.configured = configured
        self.fail = fail
        self.inspected: list[str] = []

    def credential_exists(self, provider_id: str) -> bool:
        self.inspected.append(provider_id)
        if self.fail:
            raise CredentialBackendError(provider_id, "safe synthetic failure")
        return self.configured


def _provider() -> ProviderRecord:
    return ProviderRecord(
        provider_id="nvidia-nim",
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        deployment=DeploymentType.CLOUD,
        auth=AuthConfig(type=AuthType.API_KEY, api_key_env="NVIDIA_API_KEY"),
        connection=ConnectionConfig(base_url="https://example.invalid/v1"),
        capabilities=frozenset({Capability.CHAT}),
        enabled=True,
        priority=10,
    )


def _inspect_status(
    *,
    selected_configured: bool,
    other_configured: bool = False,
    other_fails: bool = False,
    selected_target: _CredentialTarget = _CredentialTarget.COMPOSE_HOST,
) -> tuple[ProviderStatus, _MetadataBackend]:
    selected = InMemoryCredentialBackend()
    if selected_configured:
        selected.set("nvidia-nim", _SECRET)
    other = _MetadataBackend(configured=other_configured, fail=other_fails)
    other_target = (
        _CredentialTarget.WINDOWS_LOCAL
        if selected_target is _CredentialTarget.COMPOSE_HOST
        else _CredentialTarget.COMPOSE_HOST
    )
    statuses = _inspect(
        [_provider()],
        CredentialStore(selected),
        _Detector(),
        False,
        target_context=_CredentialTargetContext(
            selected=selected_target,
            other=other_target,
            other_backend=other,
        ),
    )
    return statuses["nvidia-nim"], other


class CredentialTargetStateTests(unittest.TestCase):
    def test_windows_configured_compose_missing_is_configured_other_target(self) -> None:
        status, other = _inspect_status(
            selected_configured=False,
            other_configured=True,
            selected_target=_CredentialTarget.COMPOSE_HOST,
        )

        self.assertIs(status.credential_state, _CredentialState.CONFIGURED_OTHER_TARGET)
        self.assertEqual(status.credential, "missing")
        self.assertEqual(other.inspected, ["nvidia-nim"])

    def test_compose_configured_windows_missing_is_configured_other_target(self) -> None:
        status, other = _inspect_status(
            selected_configured=False,
            other_configured=True,
            selected_target=_CredentialTarget.WINDOWS_LOCAL,
        )

        self.assertIs(status.credential_state, _CredentialState.CONFIGURED_OTHER_TARGET)
        self.assertEqual(status.credential, "missing")
        self.assertEqual(other.inspected, ["nvidia-nim"])

    def test_both_targets_configured_keeps_selected_target_authoritative(self) -> None:
        status, _ = _inspect_status(selected_configured=True, other_configured=True)

        self.assertIs(status.credential_state, _CredentialState.CONFIGURED_HERE)
        self.assertEqual(status.credential, "configured")
        self.assertTrue(status.other_target_configured)

    def test_neither_target_configured_is_missing(self) -> None:
        status, _ = _inspect_status(selected_configured=False, other_configured=False)

        self.assertIs(status.credential_state, _CredentialState.MISSING)
        self.assertEqual(status.credential, "missing")

    def test_other_target_backend_error_is_not_mapped_to_missing(self) -> None:
        status, _ = _inspect_status(selected_configured=False, other_fails=True)

        self.assertIs(status.credential_state, _CredentialState.BACKEND_ERROR)
        self.assertEqual(status.credential, "missing")
        self.assertTrue(status.other_target_error)

    def test_selected_configured_state_survives_other_target_inspection_error(self) -> None:
        status, _ = _inspect_status(selected_configured=True, other_fails=True)

        self.assertIs(status.credential_state, _CredentialState.CONFIGURED_HERE)
        self.assertEqual(status.credential, "configured")
        self.assertTrue(status.other_target_error)

    def test_selected_target_backend_error_is_not_mapped_to_missing(self) -> None:
        class _FailingSelectedBackend(InMemoryCredentialBackend):
            def get(self, provider_id: str) -> str:
                raise CredentialBackendError(provider_id, "safe synthetic failure")

        status = _inspect(
            [_provider()], CredentialStore(_FailingSelectedBackend()), _Detector(), False,
        )["nvidia-nim"]

        self.assertIs(status.credential_state, _CredentialState.BACKEND_ERROR)
        self.assertEqual(status.credential, "backend_error")

    def test_configure_and_reconfigure_gates_use_selected_target_only(self) -> None:
        status, _ = _inspect_status(selected_configured=False, other_configured=True)

        configure = _credential_mutation_eligibility(
            status, _CredentialMutationAction.CONFIGURE, read_only=False,
        )
        reconfigure = _credential_mutation_eligibility(
            status, _CredentialMutationAction.RECONFIGURE, read_only=False,
        )

        self.assertTrue(configure.allowed)
        self.assertFalse(reconfigure.allowed)

    def test_reconfigure_is_allowed_when_selected_target_is_configured(self) -> None:
        status, _ = _inspect_status(selected_configured=True, other_configured=False)

        configure = _credential_mutation_eligibility(
            status, _CredentialMutationAction.CONFIGURE, read_only=False,
        )
        reconfigure = _credential_mutation_eligibility(
            status, _CredentialMutationAction.RECONFIGURE, read_only=False,
        )

        self.assertFalse(configure.allowed)
        self.assertTrue(reconfigure.allowed)

    def test_details_explain_other_target_without_rendering_secret(self) -> None:
        status, _ = _inspect_status(selected_configured=False, other_configured=True)
        output = _Output()

        _render_provider_details(status, output)

        self.assertIn(
            "Credential: Configured in Windows local credential store", output.text,
        )
        self.assertIn(
            "This credential is not configured for Docker Compose provisioning.",
            output.text,
        )
        self.assertNotIn(_SECRET, output.text)

    def test_details_report_safe_cross_target_inspection_error(self) -> None:
        status, _ = _inspect_status(selected_configured=False, other_fails=True)
        output = _Output()

        _render_provider_details(status, output)

        self.assertIn("Credential: Inspection unavailable", output.text)
        self.assertIn("Windows local credential store could not be inspected.", output.text)
        self.assertNotIn("safe synthetic failure", output.text)
        self.assertNotIn(_SECRET, output.text)

    def test_dashboard_does_not_count_other_target_as_missing(self) -> None:
        status, _ = _inspect_status(selected_configured=False, other_configured=True)
        output = _Output()

        _render_dashboard({status.provider.provider_id: status}, output)

        self.assertIn("Configured elsewhere: 1", output.text)
        self.assertIn("Missing: 0", output.text)

    def test_dashboard_does_not_count_backend_error_as_missing(self) -> None:
        status, _ = _inspect_status(selected_configured=False, other_fails=True)
        output = _Output()

        _render_dashboard({status.provider.provider_id: status}, output)

        self.assertIn("Inspection errors: 1", output.text)
        self.assertIn("Missing: 0", output.text)


class ConcretePresenceBoundaryTests(unittest.TestCase):
    def test_reconstructed_compose_provisioner_finds_exact_provider_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret_root = root / "secrets"
            secret_root.mkdir()
            (secret_root / "nvidia-nim").write_text(_SECRET, encoding="utf-8")
            project = ComposeHostProject(root=root, secret_root=secret_root)

            first = ComposeHostCredentialProvisioner(project)
            second = ComposeHostCredentialProvisioner(project)

            self.assertTrue(first.credential_exists("nvidia-nim"))
            self.assertTrue(second.credential_exists("nvidia-nim"))

    def test_compose_presence_inspection_does_not_mutate_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret_root = root / "secrets"
            secret_root.mkdir()
            (secret_root / "nvidia-nim").write_text(_SECRET, encoding="utf-8")
            provisioner = ComposeHostCredentialProvisioner(
                ComposeHostProject(root=root, secret_root=secret_root)
            )

            with mock.patch.object(
                provisioner, "_apply_host_permissions",
            ) as apply_permissions:
                self.assertTrue(provisioner.credential_exists("nvidia-nim"))

            apply_permissions.assert_not_called()

    def test_reconstructed_windows_backend_queries_exact_guardrail_hub_target(self) -> None:
        credential = _CREDENTIAL(
            Flags=0,
            Type=CRED_TYPE_GENERIC,
            TargetName="GuardrailHub:nvidia-nim",
            Comment=None,
            CredentialBlobSize=32,
            CredentialBlob=ctypes.c_void_p(1),
            Persist=2,
            AttributeCount=0,
            Attributes=None,
            TargetAlias=None,
            UserName="GuardrailHub",
        )
        credential_pointer = ctypes.pointer(credential)

        class _Advapi32:
            def __init__(self) -> None:
                self.targets: list[tuple[str, int]] = []

            def CredReadW(self, target, credential_type, _flags, output_pointer):
                self.targets.append((target, credential_type))
                ctypes.cast(
                    output_pointer, ctypes.POINTER(ctypes.POINTER(_CREDENTIAL)),
                )[0] = credential_pointer
                return 1

            def CredFree(self, _pointer) -> None:
                return None

        api = _Advapi32()
        with mock.patch(
            "app.intelligence.credentials.windows_backend._get_advapi32",
            return_value=api,
        ):
            first = WindowsCredentialManagerBackend()
            second = WindowsCredentialManagerBackend()
            self.assertTrue(first.credential_exists("nvidia-nim"))
            self.assertTrue(second.credential_exists("nvidia-nim"))

        self.assertEqual(
            api.targets,
            [("GuardrailHub:nvidia-nim", CRED_TYPE_GENERIC)] * 2,
        )


class ResolverTargetContextTests(unittest.TestCase):
    def test_compose_selection_keeps_compose_authoritative_and_reports_windows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = ComposeHostProject(root=root, secret_root=root / "secrets")
            config = root / "llm.yaml"
            config.write_text("llm: {providers: []}\n", encoding="utf-8")
            windows = _MetadataBackend(configured=True)
            output = _Output()

            with mock.patch("app.cli.sys.platform", "win32"), mock.patch(
                "app.intelligence.setup.compose_host.recognize_compose_host_project",
                return_value=project,
            ), mock.patch(
                "app.intelligence.credentials.windows_backend.WindowsCredentialManagerBackend",
                return_value=windows,
            ):
                resolution = _resolve_store(config, output, lambda _prompt: "2", None)

            self.assertIs(
                resolution.target_context.selected, _CredentialTarget.COMPOSE_HOST,
            )
            self.assertIs(
                resolution.target_context.other, _CredentialTarget.WINDOWS_LOCAL,
            )
            status = _inspect(
                [_provider()],
                resolution.store,
                _Detector(),
                False,
                target_context=resolution.target_context,
            )["nvidia-nim"]
            self.assertEqual(status.credential, "missing")
            self.assertIs(
                status.credential_state, _CredentialState.CONFIGURED_OTHER_TARGET,
            )

    def test_windows_selection_keeps_windows_authoritative_and_reports_compose(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret_root = root / "secrets"
            secret_root.mkdir()
            (secret_root / "nvidia-nim").write_text(_SECRET, encoding="utf-8")
            project = ComposeHostProject(root=root, secret_root=secret_root)
            config = root / "llm.yaml"
            config.write_text("llm: {providers: []}\n", encoding="utf-8")
            windows = _MetadataBackend(configured=False)
            output = _Output()

            with mock.patch("app.cli.sys.platform", "win32"), mock.patch(
                "app.intelligence.setup.compose_host.recognize_compose_host_project",
                return_value=project,
            ), mock.patch(
                "app.intelligence.credentials.windows_backend.WindowsCredentialManagerBackend",
                return_value=windows,
            ):
                resolution = _resolve_store(config, output, lambda _prompt: "1", None)

            self.assertIs(
                resolution.target_context.selected, _CredentialTarget.WINDOWS_LOCAL,
            )
            self.assertIs(
                resolution.target_context.other, _CredentialTarget.COMPOSE_HOST,
            )
            status = _inspect(
                [_provider()],
                resolution.store,
                _Detector(),
                False,
                target_context=resolution.target_context,
            )["nvidia-nim"]
            self.assertEqual(status.credential, "missing")
            self.assertIs(
                status.credential_state, _CredentialState.CONFIGURED_OTHER_TARGET,
            )


if __name__ == "__main__":
    unittest.main()
