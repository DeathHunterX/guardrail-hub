"""Windows ACL boundary tests for Compose-host credential provisioning."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.intelligence.setup.windows_acl import (
    WindowsAclError,
    protect_windows_path,
)


_DUMMY_SECRET = "dummy-value-must-never-reach-acl-process"


class WindowsAclInvocationTests(unittest.TestCase):
    def test_invocation_is_fixed_shell_free_and_secret_free(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                '{"access_rules_protected":true,"principal_count":3,'
                '"principals":["S-1-5-21-1","S-1-5-18","S-1-5-32-544"]}\n'
            ),
            stderr="",
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nvidia-nim"
            target.write_bytes(b"dummy")
            with mock.patch.dict(
                os.environ, {"NVIDIA_API_KEY": _DUMMY_SECRET}
            ), mock.patch(
                "app.intelligence.setup.windows_acl._powershell_executable",
                return_value=Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"),
            ), mock.patch(
                "app.intelligence.setup.windows_acl.subprocess.run",
                return_value=completed,
            ) as run:
                protect_windows_path(target, is_directory=False)

        args, kwargs = run.call_args
        argv = args[0]
        self.assertIsInstance(argv, list)
        self.assertFalse(kwargs["shell"])
        self.assertNotIn(_DUMMY_SECRET, repr(argv))
        self.assertNotIn(_DUMMY_SECRET, kwargs["input"])
        self.assertNotIn(_DUMMY_SECRET, repr(kwargs["env"]))
        payload = json.loads(kwargs["input"])
        self.assertEqual(payload["kind"], "file")
        self.assertEqual(payload["path"], str(target.resolve()))

    def test_acl_application_failure_is_reported(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="internal failure"
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "app.intelligence.setup.windows_acl._powershell_executable",
            return_value=Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"),
        ), mock.patch(
            "app.intelligence.setup.windows_acl.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaises(WindowsAclError) as raised:
                protect_windows_path(Path(directory), is_directory=True)

        self.assertNotIn("internal failure", str(raised.exception))
        self.assertNotIn(_DUMMY_SECRET, str(raised.exception))

    def test_acl_verification_failure_is_reported(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"verified":false}\n', stderr=""
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "app.intelligence.setup.windows_acl._powershell_executable",
            return_value=Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"),
        ), mock.patch(
            "app.intelligence.setup.windows_acl.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaises(WindowsAclError):
                protect_windows_path(Path(directory), is_directory=True)


@unittest.skipUnless(os.name == "nt", "requires Windows ACL APIs")
class RealWindowsAclTests(unittest.TestCase):
    def _restrict_operator_to_modify(self, path: Path) -> None:
        """Reproduce an operator-owned directory without WRITE_OWNER access."""
        script = r"""
$ErrorActionPreference = 'Stop'
$path = [IO.Path]::GetFullPath([Console]::In.ReadToEnd())
$operator = [Security.Principal.WindowsIdentity]::GetCurrent().User
$system = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
$administrators = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$security = New-Object Security.AccessControl.DirectorySecurity
$security.SetAccessRuleProtection($true, $false)
$inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
$propagation = [Security.AccessControl.PropagationFlags]::None
[void]$security.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
    $operator,
    [Security.AccessControl.FileSystemRights]::TakeOwnership,
    [Security.AccessControl.AccessControlType]::Deny
)))
[void]$security.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
    $operator,
    [Security.AccessControl.FileSystemRights]::Modify,
    $inheritance,
    $propagation,
    [Security.AccessControl.AccessControlType]::Allow
)))
foreach ($principal in @($system, $administrators)) {
    [void]$security.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        $principal,
        [Security.AccessControl.FileSystemRights]::FullControl,
        $inheritance,
        $propagation,
        [Security.AccessControl.AccessControlType]::Allow
    )))
}
$item = Get-Item -LiteralPath $path -Force
$item.SetAccessControl($security)
$actual = $item.GetAccessControl([Security.AccessControl.AccessControlSections]::Access -bor [Security.AccessControl.AccessControlSections]::Owner)
if ($actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $operator.Value) { throw 'test owner mismatch' }
$denied = @($actual.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]) | Where-Object {
    $_.IdentityReference.Value -eq $operator.Value -and
    $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Deny -and
    ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::TakeOwnership)
})
if ($denied.Count -ne 1) { throw 'test WRITE_OWNER deny missing' }
"""
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        completed = subprocess.run(
            [
                str(Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            input=str(path.resolve()),
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_real_directory_and_file_acl_application_and_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            root.mkdir()
            target = root / "nvidia-nim"
            target.write_bytes(b"dummy")

            directory_result = protect_windows_path(root, is_directory=True)
            file_result = protect_windows_path(target, is_directory=False)

            self.assertEqual(directory_result.principal_count, 3)
            self.assertEqual(file_result.principal_count, 3)
            self.assertTrue(directory_result.access_rules_protected)
            self.assertTrue(file_result.access_rules_protected)
            self.assertEqual(
                set(directory_result.principals), set(file_result.principals)
            )

    def test_real_acl_hardening_does_not_require_write_owner_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            root.mkdir()
            self._restrict_operator_to_modify(root)

            result = protect_windows_path(root, is_directory=True)

            self.assertTrue(result.access_rules_protected)
            self.assertEqual(3, result.principal_count)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
