"""Security and behaviour tests for Compose-host credential provisioning."""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.intelligence.credentials import CredentialBackendError, CredentialNotFoundError
from app.intelligence.setup.compose_host import (
    ComposeHostCredentialProvisioner,
    recognize_compose_host_project,
)
from app.intelligence.setup.windows_acl import WindowsAclError, WindowsAclResult


_SECRET = "dummy-compose-secret-never-rendered"


def _compose_file() -> str:
    return """\
name: guardrail-hub

services:
  mcp-server:
    environment:
      GUARDRAILHUB_CREDENTIAL_BACKEND: file
    volumes:
      - ./secrets:/run/secrets:ro
"""


class _ComposeProject:
    """A real, minimal recognized project fixture rooted in a temp directory."""

    def __init__(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name) / "mcp-server"
        (self.root / "app").mkdir(parents=True)
        (self.root / "app" / "cli.py").write_text("", encoding="utf-8")
        (self.root / "config").mkdir()
        self.config = self.root / "config" / "llm.yaml"
        self.config.write_text("llm: {providers: []}\n", encoding="utf-8")
        (self.root / "docker-compose.yml").write_text(
            _compose_file(), encoding="utf-8"
        )
        (self.root / "pyproject.toml").write_text(
            """\
[project]
name = "mcp-server"
version = "0.1.0"

[project.scripts]
guardrail-hub = "app.cli:main"
""",
            encoding="utf-8",
        )

    def close(self) -> None:
        self._temporary_directory.cleanup()


class ComposeHostRecognitionTests(unittest.TestCase):
    def test_recognized_project_requires_the_ratified_file_backend_mount(self):
        project = _ComposeProject()
        self.addCleanup(project.close)

        recognized = recognize_compose_host_project(project.config)

        self.assertIsNotNone(recognized)
        assert recognized is not None
        self.assertEqual(recognized.secret_root, project.root / "secrets")

    def test_arbitrary_config_does_not_grant_a_host_secret_target(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "llm.yaml"
            config.write_text("llm: {providers: []}\n", encoding="utf-8")

            self.assertIsNone(recognize_compose_host_project(config))

    def test_minimal_lookalike_with_copied_compose_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mcp-server"
            (root / "app").mkdir(parents=True)
            (root / "app" / "cli.py").write_text("", encoding="utf-8")
            (root / "config").mkdir()
            config = root / "config" / "llm.yaml"
            config.write_text("llm: {providers: []}\n", encoding="utf-8")
            (root / "docker-compose.yml").write_text(
                _compose_file(), encoding="utf-8"
            )

            self.assertIsNone(recognize_compose_host_project(config))

    def test_wrong_project_name_is_rejected(self):
        project = _ComposeProject()
        self.addCleanup(project.close)
        (project.root / "pyproject.toml").write_text(
            """\
[project]
name = "unrelated-project"
[project.scripts]
guardrail-hub = "app.cli:main"
""",
            encoding="utf-8",
        )

        self.assertIsNone(recognize_compose_host_project(project.config))

    def test_missing_or_wrong_console_script_is_rejected(self):
        for script in (None, "other.cli:main"):
            with self.subTest(script=script):
                project = _ComposeProject()
                self.addCleanup(project.close)
                script_table = (
                    "" if script is None else f'guardrail-hub = "{script}"\n'
                )
                (project.root / "pyproject.toml").write_text(
                    "[project]\nname = \"mcp-server\"\n"
                    f"[project.scripts]\n{script_table}",
                    encoding="utf-8",
                )
                self.assertIsNone(
                    recognize_compose_host_project(project.config)
                )

    def test_missing_cli_module_is_rejected(self):
        project = _ComposeProject()
        self.addCleanup(project.close)
        (project.root / "app" / "cli.py").unlink()

        self.assertIsNone(recognize_compose_host_project(project.config))

    def test_wrong_compose_identity_or_security_contract_is_rejected(self):
        invalid_compose_files = (
            _compose_file().replace("name: guardrail-hub", "name: other"),
            _compose_file().replace("mcp-server:", "other-service:"),
            _compose_file().replace(
                "GUARDRAILHUB_CREDENTIAL_BACKEND: file", "OTHER_SETTING: file"
            ),
            _compose_file().replace("      - ./secrets:/run/secrets:ro\n", ""),
            _compose_file().replace(
                "./secrets:/run/secrets:ro", "./secrets:/run/secrets:rw"
            ),
        )
        for compose_text in invalid_compose_files:
            with self.subTest(compose_text=compose_text):
                project = _ComposeProject()
                self.addCleanup(project.close)
                (project.root / "docker-compose.yml").write_text(
                    compose_text, encoding="utf-8"
                )
                self.assertIsNone(
                    recognize_compose_host_project(project.config)
                )


class ComposeHostProvisionerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = _ComposeProject()
        recognized = recognize_compose_host_project(self.project.config)
        assert recognized is not None
        self.provisioner = ComposeHostCredentialProvisioner(recognized)

    def tearDown(self) -> None:
        self.project.close()

    def test_provisions_provider_id_file_without_rendering_secret(self):
        self.provisioner.set("nvidia-nim", _SECRET)

        target = self.project.root / "secrets" / "nvidia-nim"
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_text(encoding="utf-8"), _SECRET)
        self.assertFalse((self.project.root / "secrets" / "NVIDIA_API_KEY").exists())

    def test_existing_target_is_detected_without_reading_its_value(self):
        self.provisioner.set("nvidia-nim", _SECRET)

        self.assertEqual(self.provisioner.get("nvidia-nim"), "configured")

    def test_replacement_is_atomic_and_does_not_append_newline(self):
        target = self.project.root / "secrets" / "nvidia-nim"
        self.provisioner.set("nvidia-nim", "old")
        self.provisioner.set("nvidia-nim", _SECRET)

        self.assertEqual(target.read_bytes(), _SECRET.encode("utf-8"))

    def test_failed_replacement_preserves_the_previous_file(self):
        target = self.project.root / "secrets" / "nvidia-nim"
        self.provisioner.set("nvidia-nim", "old")

        with mock.patch("app.intelligence.setup.compose_host.os.replace", side_effect=OSError):
            with self.assertRaises(CredentialBackendError) as raised:
                self.provisioner.set("nvidia-nim", _SECRET)

        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertNotIn(_SECRET, str(raised.exception))
        self.assertEqual(list(target.parent.glob(".guardrailhub-*")), [])

    def test_cleanup_failure_is_reported_and_old_target_survives(self):
        target = self.project.root / "secrets" / "nvidia-nim"
        self.provisioner.set("nvidia-nim", "old")

        with mock.patch(
            "app.intelligence.setup.compose_host.os.replace", side_effect=OSError
        ), mock.patch(
            "app.intelligence.setup.compose_host.Path.unlink", side_effect=OSError
        ):
            with self.assertRaises(CredentialBackendError) as raised:
                self.provisioner.set("nvidia-nim", _SECRET)

        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertIn("temporary credential", str(raised.exception).lower())
        self.assertIn("operator cleanup", str(raised.exception).lower())
        self.assertNotIn(_SECRET, str(raised.exception))

    def test_successful_replacement_leaves_no_temporary_artifact(self):
        self.provisioner.set("nvidia-nim", "old")
        self.provisioner.set("nvidia-nim", _SECRET)

        self.assertEqual(
            list((self.project.root / "secrets").glob(".guardrailhub-*")), []
        )

    @unittest.skipUnless(os.name == "nt", "requires Windows provisioning path")
    def test_windows_acl_application_failure_preserves_old_credential(self):
        target = self.project.root / "secrets" / "nvidia-nim"
        self.provisioner.set("nvidia-nim", "old")

        with mock.patch(
            "app.intelligence.setup.compose_host.protect_windows_path",
            side_effect=WindowsAclError("ACL application failed"),
        ):
            with self.assertRaises(CredentialBackendError) as raised:
                self.provisioner.set("nvidia-nim", _SECRET)

        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertEqual(list(target.parent.glob(".guardrailhub-*")), [])
        self.assertNotIn(_SECRET, str(raised.exception))

    @unittest.skipUnless(os.name == "nt", "requires Windows provisioning path")
    def test_windows_file_acl_verification_failure_preserves_old_credential(self):
        target = self.project.root / "secrets" / "nvidia-nim"
        self.provisioner.set("nvidia-nim", "old")
        verified = WindowsAclResult(
            access_rules_protected=True,
            principal_count=3,
            principals=("operator", "system", "administrators"),
        )

        with mock.patch(
            "app.intelligence.setup.compose_host.protect_windows_path",
            side_effect=[verified, WindowsAclError("ACL verification failed")],
        ):
            with self.assertRaises(CredentialBackendError):
                self.provisioner.set("nvidia-nim", _SECRET)

        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertEqual(list(target.parent.glob(".guardrailhub-*")), [])

    def test_secret_root_symlink_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable on this platform")
        outside = self.project.root / "outside"
        outside.mkdir()
        try:
            (self.project.root / "secrets").symlink_to(
                outside, target_is_directory=True
            )
        except OSError as exc:
            self.skipTest(f"directory symlink creation unavailable: {exc}")

        with self.assertRaises(CredentialBackendError):
            self.provisioner.set("nvidia-nim", _SECRET)
        self.assertFalse((outside / "nvidia-nim").exists())

    def test_unsafe_provider_ids_cannot_escape_the_secret_root(self):
        for provider_id in ("", " ", "../outside", "nested/name", "..", "C:\\outside", "bad\x00id"):
            with self.subTest(provider_id=repr(provider_id)):
                with self.assertRaises(CredentialBackendError):
                    self.provisioner.set(provider_id, _SECRET)

        self.assertFalse((self.project.root / "outside").exists())

    def test_symlink_target_is_refused(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable on this platform")
        secret_root = self.project.root / "secrets"
        secret_root.mkdir()
        target = secret_root / "nvidia-nim"
        outside = self.project.root / "outside"
        outside.write_text("old", encoding="utf-8")
        try:
            target.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

        with self.assertRaises(CredentialBackendError):
            self.provisioner.set("nvidia-nim", _SECRET)
        self.assertEqual(outside.read_text(encoding="utf-8"), "old")

    def test_oversized_secret_is_rejected_without_creating_a_file(self):
        oversized = "x" * (64 * 1024 + 1)

        with self.assertRaises(CredentialBackendError):
            self.provisioner.set("nvidia-nim", oversized)

        self.assertFalse((self.project.root / "secrets" / "nvidia-nim").exists())

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not portable")
    def test_posix_secret_directory_and_file_are_owner_only(self):
        self.provisioner.set("nvidia-nim", _SECRET)
        secret_root = self.project.root / "secrets"
        target = secret_root / "nvidia-nim"

        self.assertEqual(stat.S_IMODE(secret_root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_missing_target_is_reported_without_creating_the_directory(self):
        with self.assertRaises(CredentialNotFoundError):
            self.provisioner.get("nvidia-nim")
        self.assertFalse((self.project.root / "secrets").exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
