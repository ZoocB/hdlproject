"""Tests for cooperative cancellation primitives."""

import logging
import subprocess
import time

import pytest

from hdlproject.core.cancellation import CancellationToken, terminate_process_group

LOG = logging.getLogger("test.cancellation")


def test_token_starts_uncancelled():
    token = CancellationToken()
    assert not token.cancelled
    assert token.wait(0.01) is False


def test_token_cancel_is_observable_and_idempotent():
    token = CancellationToken()
    token.cancel()
    token.cancel()  # idempotent
    assert token.cancelled
    assert token.wait(0.01) is True


def test_terminate_process_group_kills_running_process():
    # New session so the child leads its own group (mirrors the executor).
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    assert proc.poll() is None

    terminate_process_group(proc, LOG, grace=5.0)

    # Process must be reaped, not orphaned.
    assert proc.poll() is not None


def test_terminate_process_group_noop_on_finished_process():
    proc = subprocess.Popen(["true"], start_new_session=True)
    proc.wait()
    # Should not raise even though the process already exited.
    terminate_process_group(proc, LOG, grace=1.0)
    assert proc.poll() is not None


def test_terminate_kills_child_processes_too():
    # A shell that spawns a child sleep; killing only the shell would orphan it.
    proc = subprocess.Popen(
        ["bash", "-c", "sleep 30 & wait"], start_new_session=True
    )
    time.sleep(0.2)
    terminate_process_group(proc, LOG, grace=5.0)
    assert proc.poll() is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
