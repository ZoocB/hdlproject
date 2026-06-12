"""Progress reporting seam between the execution core and a front-end.

``VivadoOutputProcessor`` (and ``ToolExecutorService``) drive a *sink* during a
run rather than a concrete display. This decouples the execution core from how
progress is rendered: today the only implementation is
:class:`~hdlproject.utils.rich_sink.RichLiveSink` (the live Rich tree), but the
``Protocol`` keeps the door open for an alternative front-end without touching
the engine.

The method surface here is exactly what the core calls during a run; lifecycle
concerns (creating projects, starting/stopping the display, log-file paths) stay
with ``StatusManager``. Keeping this a ``Protocol`` (structural typing) means
sinks don't need to inherit anything — they just implement the methods.
"""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ProgressSink(Protocol):
    """What the execution core emits to as a run progresses.

    Implementations must be safe to call from worker threads (the Rich sink
    relies on Rich's thread-safe ``Live``). All methods are keyed by
    ``project_name`` so a single sink can track several projects building in
    parallel.
    """

    def start_project(self, project_name: str) -> None:
        """Transition a project from pending to running."""
        ...

    def update_project_step(
        self,
        project_name: str,
        step_name: str,
        failed: bool = False,
        message: Optional[str] = None,
        warning_count: int = 0,
        critical_warning_count: int = 0,
        error_count: int = 0,
        step_result: Optional[str] = None,
    ) -> None:
        """Advance/complete a step. ``step_result`` is one of
        ``'success' | 'warning' | 'error'`` (or ``None`` to just start it);
        ``failed`` marks the step failed without failing the whole project."""
        ...

    def complete_project(
        self,
        project_name: str,
        success: bool = True,
        message: Optional[str] = None,
    ) -> None:
        """Mark a project finished. Warnings do not count as failure."""
        ...

    def set_project_context_name(self, project_name: str, context_name: str) -> None:
        """Record the resolved build/artefact name reported by the TCL flow."""
        ...

    def set_build_artefacts_path(self, project_name: str, artefacts_path: str) -> None:
        """Record where the build wrote its artefacts."""
        ...

    def set_extra_info(
        self,
        project_name: str,
        key: str,
        label: str,
        value: str,
        style: str = "dim",
        path: Optional[str] = None,
    ) -> None:
        """Attach a labelled extra fact to a project (e.g. timing PASSED/FAILED)."""
        ...

    def process_output(self, line: str, project_name: str) -> None:
        """Raw output-line hook. Used by interactive front-ends to stream the
        live log; the batch sink ignores it (it writes its own log file)."""
        ...
