"""Cooperative cancellation for long-running tool processes.

A :class:`CancellationToken` is a thin wrapper over ``threading.Event`` shared
between whoever requests cancellation (a Ctrl+C handler in batch mode, or the
Textual "cancel" binding) and the executor watching it. ``terminate_process_group``
tears down a Vivado process *and its children* by signalling the whole process
group, escalating SIGINT → SIGTERM → SIGKILL — Vivado spawns sub-processes, so
killing just the immediate child would orphan them.
"""

import os
import signal
import subprocess
import threading


class CancellationToken:
    """A shareable, thread-safe cancellation flag."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation. Idempotent."""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        """Block up to ``timeout`` seconds; return True if cancelled meanwhile."""
        return self._event.wait(timeout)


def terminate_process_group(
    process: subprocess.Popen,
    logger,
    grace: float = 5.0,
) -> None:
    """Terminate ``process`` and its process group, escalating signals.

    The process must have been started with ``start_new_session=True`` so it is
    the leader of its own group. Safe to call if the process already exited.
    """
    if process.poll() is not None:
        return

    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=grace)
            logger.info(f"Process group terminated via {sig.name}")
            return
        except subprocess.TimeoutExpired:
            logger.warning(
                f"Process group did not exit after {sig.name}; escalating"
            )
    logger.error("Process group survived SIGKILL escalation")
