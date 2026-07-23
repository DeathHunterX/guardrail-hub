"""Run one child process in its own process group, with timeout & cancellation.

This is the subprocess machinery of the JMeter Runner (INV7: ``subprocess`` lives
only in the Runner). It exists so that INV8 holds: the engine is launched as a
**process-group leader** (``start_new_session=True``), and when the policy
timeout elapses or cancellation is observed, the **entire group** is signalled —
``SIGTERM``, a grace period, then ``SIGKILL`` — never just the parent. That is
what prevents a killed JMeter run from leaving orphaned child processes behind
(orphan count is a worker health metric precisely because leaks must be visible).

POSIX-only by design: the worker runs on Linux. stdout/stderr are redirected to
files (not pipes) so a group kill can never deadlock on a full pipe buffer.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Event
from typing import Optional, Sequence


class ProcessTermination(str, Enum):
    """Why the process stopped."""

    FINISHED = "finished"     # exited on its own (see exit_code)
    TIMED_OUT = "timed_out"   # timeout elapsed; group killed
    CANCELLED = "cancelled"   # cancellation observed; group killed


@dataclass(frozen=True)
class ProcessOutcome:
    termination: ProcessTermination
    exit_code: Optional[int]


_DEFAULT_GRACE_SECONDS = 10.0
_DEFAULT_POLL_SECONDS = 0.1


def run_in_process_group(
    command: Sequence[str],
    *,
    timeout_seconds: Optional[float],
    cancel: Event,
    stdout_path: Path,
    stderr_path: Path,
    grace_seconds: float = _DEFAULT_GRACE_SECONDS,
    poll_seconds: float = _DEFAULT_POLL_SECONDS,
) -> ProcessOutcome:
    """Launch *command* in its own process group and supervise it.

    Returns when the process exits on its own (``FINISHED`` + its exit code), or
    after the whole group has been terminated because *cancel* was set
    (``CANCELLED``) or *timeout_seconds* elapsed (``TIMED_OUT``). Raises
    ``FileNotFoundError`` if *command*'s binary does not exist (an infrastructure
    fault the caller maps to a failed result).
    """
    with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
        proc = subprocess.Popen(  # noqa: S603 - command is built by the Runner, not user input
            list(command),
            stdout=out,
            stderr=err,
            start_new_session=True,  # new session => own process group (INV8)
        )

    deadline = time.monotonic() + timeout_seconds if timeout_seconds else None
    try:
        while True:
            code = proc.poll()
            if code is not None:
                return ProcessOutcome(ProcessTermination.FINISHED, code)
            if cancel.is_set():
                _terminate_group(proc, grace_seconds)
                return ProcessOutcome(ProcessTermination.CANCELLED, proc.returncode)
            if deadline is not None and time.monotonic() >= deadline:
                _terminate_group(proc, grace_seconds)
                return ProcessOutcome(ProcessTermination.TIMED_OUT, proc.returncode)
            time.sleep(poll_seconds)
    finally:
        # Belt and braces: never leave the group running on any exit path.
        if proc.poll() is None:
            _terminate_group(proc, grace_seconds)


def _terminate_group(proc: subprocess.Popen, grace_seconds: float) -> None:
    """SIGTERM the whole group, wait a grace period, then SIGKILL if needed."""
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return  # already gone
    _signal_group(pgid, signal.SIGTERM)
    if _wait(proc, grace_seconds):
        return
    _signal_group(pgid, signal.SIGKILL)
    _wait(proc, grace_seconds)


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass  # group already reaped


def _wait(proc: subprocess.Popen, timeout: float) -> bool:
    """Wait up to *timeout* for exit; True if it exited, False if still running."""
    try:
        proc.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        return False
