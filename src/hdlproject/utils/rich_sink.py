# utils/rich_sink.py
"""Batch-CLI progress sink: a live Rich tree of projects and their steps.

``RichLiveSink`` implements :class:`~hdlproject.core.progress.ProgressSink` for
non-interactive (CLI) runs. It owns a Rich ``Live`` display and a daemon thread
that re-renders the shared :mod:`progress_model` state a few times a second, and
prints a final summary when stopped. ``StatusManager`` constructs one of these
only when a status display should be shown; otherwise the execution core runs
with ``sink=None``.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.tree import Tree

from hdlproject.core.progress_model import (
    ExtraInfoItem,
    MessageLevel,
    ProjectStatus,
    Step,
    StepState,
)
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class RichLiveSink:
    """Live status display rendered as a Rich tree (the CLI front-end).

    Implements :class:`~hdlproject.core.progress.ProgressSink`: it tracks the
    per-project state (a dict of :class:`ProjectStatus`) and renders it as a Rich
    ``Live`` tree, refreshed by a daemon thread, with a final summary on stop.
    ``StatusManager`` builds one when a status display should be shown; otherwise
    the execution core runs with ``sink=None``.
    """

    def __init__(self, title: str):
        self.title = title
        self.projects: dict[str, ProjectStatus] = {}
        self._lock = threading.RLock()
        self._running = False

        self.console = Console()
        self.live: Optional[Live] = None
        self._display_thread: Optional[threading.Thread] = None

    # === ProgressSink: registration + mutations ===

    def add_project(self, project_name: str, steps: list[str]) -> None:
        """Register a project with its predefined steps."""
        with self._lock:
            self.projects[project_name] = ProjectStatus(
                name=project_name, steps=[Step(name=s) for s in steps]
            )

    def set_project_log_file(self, project_name: str, log_file_path: str) -> None:
        """Set the log file path for a project."""
        with self._lock:
            if project_name in self.projects:
                self.projects[project_name].log_file_path = log_file_path

    def start_project(self, project_name: str) -> None:
        """Transition a project from pending to running."""
        with self._lock:
            project = self.projects.get(project_name)
            if project is None:
                logger.warning(f"Cannot start unknown project: {project_name}")
                return
            if project.overall_state == StepState.PENDING:
                project.overall_state = StepState.RUNNING
                project.start_time = datetime.now()

    def set_project_context_name(self, project_name: str, context_name: str) -> None:
        """Record the resolved build/artefact name for a project."""
        with self._lock:
            if project_name in self.projects:
                self.projects[project_name].project_context_name = context_name

    def set_build_artefacts_path(self, project_name: str, artefacts_path: str) -> None:
        """Record where the build wrote its artefacts."""
        with self._lock:
            if project_name in self.projects:
                self.projects[project_name].build_artefacts_path = artefacts_path

    def set_extra_info(
        self,
        project_name: str,
        key: str,
        label: str,
        value: str,
        style: str = "dim",
        path: Optional[str] = None,
    ) -> None:
        """Attach a labelled extra fact (e.g. timing PASSED/FAILED) to a project."""
        with self._lock:
            if project_name in self.projects:
                self.projects[project_name].extra_info[key] = ExtraInfoItem(
                    label=label, value=value, style=style, path=path
                )

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
        """Advance/complete a step with an optional result state."""
        with self._lock:
            project = self.projects.get(project_name)
            if project is None:
                return

            if not project.start_time:
                project.start_time = datetime.now()
                project.overall_state = StepState.RUNNING

            if failed:
                project.mark_step_failed(step_name, error_count)
            elif step_result == "warning":
                project.complete_step_with_result(
                    step_name, StepState.WARNING,
                    warning_count, critical_warning_count, error_count,
                )
            elif step_result == "error":
                project.mark_step_failed(step_name, error_count)
            elif step_result == "success":
                project.complete_step_with_result(
                    step_name, StepState.COMPLETED,
                    warning_count, critical_warning_count, 0,
                )
            else:
                project.start_step(step_name)

    def complete_project(
        self, project_name: str, success: bool = True, message: Optional[str] = None
    ) -> None:
        """Mark a project completed. Warnings do not affect success."""
        with self._lock:
            project = self.projects.get(project_name)
            if project is None:
                return
            if success:
                project.complete(with_warnings=False)
            else:
                project.fail(message)

    def process_output(self, line: str, project_name: str) -> None:
        """Raw output-line hook. The batch display renders from step state and
        writes its own log file, so this is intentionally a no-op."""

    # === Lifecycle (driven by StatusManager) ===

    def start_display(self) -> None:
        """Start the Rich Live display and its refresh thread."""
        self._running = True
        self.live = Live(
            self._generate_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
            screen=True,
        )
        self.live.start()

        self._display_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._display_thread.start()

    def stop_display(self) -> None:
        """Stop the display and print the final summary."""
        self._running = False

        if self._display_thread:
            self._display_thread.join(timeout=1.0)

        if self.live:
            try:
                self.live.update(self._generate_display())
                time.sleep(0.5)
                self.live.stop()
                self._print_final_summary()
            except Exception as e:
                logger.debug(f"Error finalising status display: {e}")

    # === Rendering ===

    def _update_loop(self) -> None:
        """Refresh the Rich display until stopped."""
        while self._running and self.live:
            try:
                self.live.update(self._generate_display())
                time.sleep(0.25)
            except Exception as e:
                logger.debug(f"Status display update failed: {e}")

    def _print_final_summary(self) -> None:
        from rich.rule import Rule

        console = Console()

        with self._lock:
            failed = [
                p for p in self.projects.values() if p.overall_state == StepState.FAILED
            ]
            succeeded = [
                p for p in self.projects.values() if p.overall_state != StepState.FAILED
            ]

            style = "red" if failed else "green"
            status = "FAILED" if failed else "SUCCESS"

            print()
            console.print(
                Rule(
                    f"[bold]{self.title.replace(' Operations', '')}[/bold]", style=style
                )
            )

            parts = [f"[bold {style}]{status}[/bold {style}]"]
            if failed:
                parts.append(f"{len(failed)} failed")
            if succeeded:
                parts.append(f"{len(succeeded)} succeeded")
            console.print(" · ".join(parts))
            console.print()

            for name, project in sorted(self.projects.items()):
                has_issues = (
                    project.has_issues() or project.overall_state == StepState.FAILED
                )
                if not has_issues and failed:
                    continue

                display_name = project.project_context_name or name
                if project.overall_state == StepState.FAILED:
                    console.print(
                        f"[red]✗[/red] [bold red]{display_name}[/bold red]", end=""
                    )
                else:
                    console.print(
                        f"[green]✓[/green] [bold green]{display_name}[/bold green]",
                        end="",
                    )

                counts = (
                    [f"{project.total_warnings}W"] if project.total_warnings else []
                )
                counts += (
                    [f"{project.total_critical_warnings}CW"]
                    if project.total_critical_warnings
                    else []
                )
                counts += [f"{project.total_errors}E"] if project.total_errors else []
                console.print(f" [dim][{'/'.join(counts)}][/dim]" if counts else "")

                for step in project.steps:
                    if step.state == StepState.FAILED:
                        console.print(
                            f"  [red]✗ {step.name}[/red] "
                            f"[dim][{step.get_count_str()}][/dim]"
                            if step.get_count_str()
                            else f"  [red]✗ {step.name}[/red]"
                        )
                    elif step.has_issues():
                        console.print(
                            f"  [yellow]⚠ {step.name}[/yellow] "
                            f"[dim][{step.get_count_str()}][/dim]"
                        )

                for info in project.extra_info.values():
                    console.print(
                        f"  [dim]{info.label}[/dim] "
                        f"[{info.style}]{info.value}[/{info.style}]"
                    )
                    if info.path:
                        print(f"  Report {info.path}")  # Plain print - no wrapping

                if project.build_artefacts_path:
                    print(f"  Artefacts {project.build_artefacts_path}")  # Plain print
                if project.log_file_path:
                    print(f"  Log {project.log_file_path}")  # Plain print

            console.print()
            print(f"App Log {Path.cwd() / 'bin' / 'hdlproject.log'}")  # Plain print
            console.print(Rule(style=style))

    def _generate_display(self) -> Panel:
        """Generate the Rich tree panel.

        Projects with warnings are grouped under 'Completed' (success), not a
        separate 'Warning' category — Vivado always emits warnings.
        """
        with self._lock:
            tree = Tree(f"[bold cyan]{self.title}[/bold cyan]")

            # Group projects by state - WARNING is treated as COMPLETED
            groups: dict[StepState, list[tuple[str, ProjectStatus]]] = {
                StepState.RUNNING: [],
                StepState.COMPLETED: [],
                StepState.FAILED: [],
                StepState.PENDING: [],
            }

            for name, project in self.projects.items():
                state = project.overall_state
                # Treat WARNING as COMPLETED for grouping: Vivado always produces
                # warnings, so a permanent warning bucket would just be noise.
                if state == StepState.WARNING:
                    state = StepState.COMPLETED
                groups[state].append((name, project))

            state_theme = {
                StepState.PENDING: ("○", "dim white"),
                StepState.RUNNING: ("►", "cyan"),
                StepState.COMPLETED: ("✓", "green"),
                StepState.FAILED: ("✗", "red"),
                StepState.SKIPPED: ("—", "dim yellow"),
            }

            step_theme = {
                StepState.PENDING: ("·", "dim white"),
                StepState.RUNNING: ("►", "cyan"),
                StepState.COMPLETED: ("✓", "green"),
                StepState.WARNING: ("⚠", "yellow"),
                StepState.FAILED: ("✗", "red"),
                StepState.SKIPPED: ("—", "dim yellow"),
            }

            display_order = [
                StepState.RUNNING,
                StepState.FAILED,
                StepState.COMPLETED,
                StepState.PENDING,
            ]

            for state in display_order:
                projects = groups[state]
                if not projects:
                    continue

                symbol, color = state_theme[state]
                state_name = state.name.title()
                branch = tree.add(
                    f"[{color}]{symbol} {state_name} ({len(projects)})[/{color}]"
                )

                for name, project in sorted(projects):
                    project_text = f"[bold]{name}[/bold]"

                    msg_summary = project.get_message_summary()
                    if msg_summary:
                        project_text += f" [dim][{msg_summary}][/dim]"

                    if state == StepState.RUNNING:
                        project_text += f" [{project.get_elapsed_time()}]"

                    if state == StepState.RUNNING and project.steps:
                        project_branch = branch.add(project_text)

                        for step in project.steps:
                            if step.state != StepState.PENDING:
                                step_symbol, step_color = step_theme[step.state]
                                duration = (
                                    f" ({step.get_duration_str()})"
                                    if step.get_duration_str()
                                    else ""
                                )
                                count_str = step.get_count_str()
                                count_display = f" [{count_str}]" if count_str else ""
                                project_branch.add(
                                    f"[{step_color}]{step_symbol} {step.name}"
                                    f"{duration}{count_display}[/{step_color}]"
                                )

                        latest_msg = project.get_latest_message()
                        if latest_msg:
                            msg_color = {
                                MessageLevel.INFO: "white",
                                MessageLevel.WARNING: "yellow",
                                MessageLevel.ERROR: "red",
                                MessageLevel.CRITICAL: "bold orange3",
                            }.get(latest_msg.level, "white")
                            msg_text = latest_msg.message
                            if len(msg_text) > 60:
                                msg_text = msg_text[:57] + "..."
                            project_branch.add(
                                f"[{msg_color}]├─ {msg_text}[/{msg_color}]"
                            )

                        if project.log_file_path:
                            project_branch.add(
                                f"[dim cyan]└─ Log: "
                                f"{project.log_file_path}[/dim cyan]"
                            )
                    else:
                        text = project_text
                        if project.message:
                            text += f" [dim]- {project.message}[/dim]"

                        if state == StepState.FAILED or (
                            state == StepState.COMPLETED and msg_summary
                        ):
                            project_branch = branch.add(text)

                            for step in project.steps:
                                if step.state == StepState.FAILED or step.has_issues():
                                    step_symbol, step_color = step_theme.get(
                                        step.state, ("⚠", "yellow")
                                    )
                                    if (
                                        step.state != StepState.FAILED
                                        and step.has_issues()
                                    ):
                                        step_symbol, step_color = "⚠", "yellow"
                                    count_str = step.get_count_str()
                                    count_display = (
                                        f" [{count_str}]" if count_str else ""
                                    )
                                    project_branch.add(
                                        f"[{step_color}]{step_symbol} "
                                        f"{step.name}{count_display}[/{step_color}]"
                                    )

                            for info in project.extra_info.values():
                                project_branch.add(
                                    f"[dim]{info.label}[/dim] "
                                    f"[{info.style}]{info.value}[/{info.style}]"
                                )

                            if project.log_file_path:
                                project_branch.add(
                                    f"[dim cyan]└─ Log: "
                                    f"{project.log_file_path}[/dim cyan]"
                                )
                        else:
                            branch.add(text)

            return Panel(
                tree, border_style="blue", box=box.ROUNDED, subtitle_align="right"
            )
