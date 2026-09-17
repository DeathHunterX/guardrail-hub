"""Windows ACL enforcement for Compose-host secret provisioning.

This is a narrow operator-host adapter, not a runtime credential backend.  It
uses the built-in Windows PowerShell/.NET access-control API because Python's
``chmod`` cannot establish or verify a protected DACL.  The fixed script
receives only an absolute path and object kind; credential content never enters
argv, stdin, the subprocess environment, or diagnostic output.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final


class WindowsAclError(OSError):
    """The required protected Windows ACL could not be applied or verified."""


@dataclass(frozen=True, slots=True)
class WindowsAclResult:
    """Secret-free semantic verification returned by the ACL adapter."""

    access_rules_protected: bool
    principal_count: int
    principals: tuple[str, ...]


_SYSTEM_SID: Final[str] = "S-1-5-18"
_ADMINISTRATORS_SID: Final[str] = "S-1-5-32-544"
_SUCCESS_FIELDS: Final[frozenset[str]] = frozenset(
    {"access_rules_protected", "principal_count", "principals"}
)

# Fixed PowerShell logic. Input is JSON path metadata only, read from stdin.
# The DACL is rebuilt from scratch with inheritance disabled, so unknown or
# inherited ACEs cannot survive. FullControl is intentional: the operator must
# atomically replace/delete the file; SYSTEM and Administrators are the
# unavoidable Windows recovery/administration identities ratified for this
# local-host contract.
_POWERSHELL_SCRIPT: Final[str] = r"""
$ErrorActionPreference = 'Stop'
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$path = [IO.Path]::GetFullPath([string]$payload.path)
$isDirectory = ([string]$payload.kind -eq 'directory')

$operator = [Security.Principal.WindowsIdentity]::GetCurrent().User
$system = New-Object Security.Principal.SecurityIdentifier('S-1-5-18')
$administrators = New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$principals = @($operator, $system, $administrators)

if ($isDirectory) {
    $security = New-Object Security.AccessControl.DirectorySecurity
    $inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
} else {
    $security = New-Object Security.AccessControl.FileSecurity
    $inheritance = [Security.AccessControl.InheritanceFlags]::None
}
$propagation = [Security.AccessControl.PropagationFlags]::None
$security.SetAccessRuleProtection($true, $false)
# Do not write the owner field. An operator who owns a directory can replace
# its DACL without holding WRITE_OWNER; requesting the unchanged owner would
# make otherwise-valid hardening fail with UnauthorizedAccessException.
foreach ($principal in $principals) {
    $rule = New-Object Security.AccessControl.FileSystemAccessRule(
        $principal,
        [Security.AccessControl.FileSystemRights]::FullControl,
        $inheritance,
        $propagation,
        [Security.AccessControl.AccessControlType]::Allow
    )
    [void]$security.AddAccessRule($rule)
}

$item = Get-Item -LiteralPath $path -Force
$item.SetAccessControl($security)
$actual = $item.GetAccessControl([Security.AccessControl.AccessControlSections]::Access -bor [Security.AccessControl.AccessControlSections]::Owner)
$rules = @($actual.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
$expectedSids = @($operator.Value, $system.Value, $administrators.Value)

if (-not $actual.AreAccessRulesProtected) { throw 'ACL inheritance is not protected' }
if ($actual.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $operator.Value) { throw 'ACL owner mismatch' }
if ($rules.Count -ne 3) { throw 'ACL principal count mismatch' }
foreach ($rule in $rules) {
    if ($rule.IsInherited) { throw 'Inherited ACE remains' }
    if ($expectedSids -notcontains $rule.IdentityReference.Value) { throw 'Unexpected ACL principal' }
    if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) { throw 'Unexpected ACL type' }
    if ($rule.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl) { throw 'Unexpected ACL rights' }
    if ($rule.PropagationFlags -ne $propagation) { throw 'Unexpected propagation flags' }
    if ($rule.InheritanceFlags -ne $inheritance) { throw 'Unexpected inheritance flags' }
}

@{
    access_rules_protected = $actual.AreAccessRulesProtected
    principal_count = $rules.Count
    principals = @($rules | ForEach-Object { $_.IdentityReference.Value } | Sort-Object)
} | ConvertTo-Json -Compress
"""
_ENCODED_POWERSHELL_SCRIPT: Final[str] = base64.b64encode(
    _POWERSHELL_SCRIPT.encode("utf-16-le")
).decode("ascii")


def protect_windows_path(path: Path, *, is_directory: bool) -> WindowsAclResult:
    """Apply and semantically verify the required protected Windows ACL."""
    try:
        resolved = path.resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise WindowsAclError("Windows ACL target is unavailable") from exc
    if resolved.is_dir() != is_directory:
        raise WindowsAclError("Windows ACL target type is invalid")

    payload = json.dumps(
        {"path": str(resolved), "kind": "directory" if is_directory else "file"},
        separators=(",", ":"),
    )
    try:
        completed = subprocess.run(
            [
                str(_powershell_executable()),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                _ENCODED_POWERSHELL_SCRIPT,
            ],
            input=payload,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=30,
            env=_windows_subprocess_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WindowsAclError("Windows ACL application failed") from exc
    if completed.returncode != 0:
        raise WindowsAclError("Windows ACL application or verification failed")

    try:
        result = json.loads(completed.stdout)
        if not isinstance(result, dict) or frozenset(result) != _SUCCESS_FIELDS:
            raise ValueError("unexpected result shape")
        protected = result["access_rules_protected"]
        count = result["principal_count"]
        principals = result["principals"]
        if protected is not True or count != 3 or not isinstance(principals, list):
            raise ValueError("verification result mismatch")
        if not {_SYSTEM_SID, _ADMINISTRATORS_SID}.issubset(set(principals)):
            raise ValueError("required principal missing")
        if len(principals) != 3 or not all(isinstance(item, str) for item in principals):
            raise ValueError("unexpected principals")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise WindowsAclError("Windows ACL verification failed") from exc
    return WindowsAclResult(
        access_rules_protected=True,
        principal_count=3,
        principals=tuple(principals),
    )


def _powershell_executable() -> Path:
    """Resolve the fixed inbox Windows PowerShell executable."""
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if not system_root:
        raise WindowsAclError("Windows system root is unavailable")
    executable = (
        Path(system_root)
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    if not executable.is_file():
        raise WindowsAclError("Windows PowerShell is unavailable")
    return executable


def _windows_subprocess_environment() -> dict[str, str]:
    """Return a minimal, secret-free environment for the ACL subprocess."""
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if not system_root:
        raise WindowsAclError("Windows system root is unavailable")
    system32 = str(Path(system_root) / "System32")
    result = {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "PATH": system32,
    }
    for name in ("TEMP", "TMP"):
        value = os.environ.get(name)
        if value:
            result[name] = value
    return result


__all__ = ["WindowsAclError", "WindowsAclResult", "protect_windows_path"]
