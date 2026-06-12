"""Pure progress state model (no rendering dependencies).

These dataclasses hold the live state of an operation — projects, their steps and
accumulated warning/error counts — with thread-safe mutators. They carry no Rich
or Textual imports, so any front-end (the batch ``RichLiveSink`` or the Textual
dashboard) can render the same state. The mutator semantics here are the contract
the ``ProgressSink`` implementations build on.
"""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class StepState(Enum):
    """States for individual steps."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


class MessageLevel(Enum):
    """Message severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Step:
    """Individual step in a process."""

    name: str
    state: StepState = StepState.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    warning_count: int = 0
    critical_warning_count: int = 0
    error_count: int = 0

    def get_duration_str(self) -> str:
        """Get formatted duration string."""
        if not self.start_time:
            return ""

        end_time = self.end_time or datetime.now()
        duration = int((end_time - self.start_time).total_seconds())

        if duration < 60:
            return f"{duration}s"
        else:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes:02d}:{seconds:02d}"

    def get_count_str(self) -> str:
        """Get warning/critical warning/error count string."""
        parts = []
        if self.warning_count > 0:
            parts.append(f"W:{self.warning_count}")
        if self.critical_warning_count > 0:
            parts.append(f"CW:{self.critical_warning_count}")
        if self.error_count > 0:
            parts.append(f"E:{self.error_count}")
        return " ".join(parts) if parts else ""

    def has_issues(self) -> bool:
        """Check if step has any warnings, critical warnings, or errors."""
        return (
            self.warning_count > 0
            or self.critical_warning_count > 0
            or self.error_count > 0
        )


@dataclass
class ExtraInfoItem:
    """Generic extra information item for display."""

    label: str  # e.g., "Timing"
    value: str  # e.g., "PASSED"
    style: str = "dim"  # Rich style: "green", "red", "yellow", "dim", etc.
    path: Optional[str] = None  # Optional path to display (e.g., report file)


@dataclass
class ProjectMessage:
    """Message associated with a project."""

    level: MessageLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProjectStatus:
    """Status tracking for a single project."""

    name: str
    steps: list[Step] = field(default_factory=list)
    current_step_index: int = -1
    overall_state: StepState = StepState.PENDING
    start_time: Optional[datetime] = None
    message: Optional[str] = None
    log_file_path: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # Message tracking
    messages: list[ProjectMessage] = field(default_factory=list)
    message_counts: dict[MessageLevel, int] = field(
        default_factory=lambda: defaultdict(int)
    )

    # Overall counts
    total_warnings: int = 0
    total_critical_warnings: int = 0
    total_errors: int = 0

    # Project context info
    project_context_name: Optional[str] = None
    build_artefacts_path: Optional[str] = None

    # Generic extra info (for timing results, etc.)
    extra_info: dict[str, ExtraInfoItem] = field(default_factory=dict)

    def get_elapsed_time(self) -> str:
        """Get total elapsed time."""
        if not self.start_time:
            return "00:00"

        elapsed = (datetime.now() - self.start_time).total_seconds()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def add_message(self, level: MessageLevel, message: str) -> None:
        """Add a message to this project."""
        with self._lock:
            self.messages.append(ProjectMessage(level, message))
            self.message_counts[level] += 1

    def get_latest_message(self) -> Optional[ProjectMessage]:
        """Get the most recent warning/critical/error message."""
        with self._lock:
            relevant_messages = [
                msg
                for msg in self.messages
                if msg.level
                in [MessageLevel.WARNING, MessageLevel.ERROR, MessageLevel.CRITICAL]
            ]
            return relevant_messages[-1] if relevant_messages else None

    def get_message_summary(self) -> str:
        """Get message count summary with separate W/CW/E."""
        with self._lock:
            parts = []
            if self.total_warnings > 0:
                parts.append(f"W:{self.total_warnings}")
            if self.total_critical_warnings > 0:
                parts.append(f"CW:{self.total_critical_warnings}")
            if self.total_errors > 0:
                parts.append(f"E:{self.total_errors}")
            return " ".join(parts) if parts else ""

    def has_issues(self) -> bool:
        """Check if project has any warnings, critical warnings, or errors."""
        return (
            self.total_warnings > 0
            or self.total_critical_warnings > 0
            or self.total_errors > 0
        )

    def start_step(self, step_name: str) -> None:
        """Start a specific step - thread-safe."""
        with self._lock:
            # Complete current step if running
            if self.current_step_index >= 0:
                current = self.steps[self.current_step_index]
                if current.state == StepState.RUNNING:
                    current.state = StepState.COMPLETED
                    current.end_time = datetime.now()

            # Find and start the new step
            for i, step in enumerate(self.steps):
                if step.name == step_name:
                    # Mark skipped steps
                    for j in range(self.current_step_index + 1, i):
                        if self.steps[j].state == StepState.PENDING:
                            self.steps[j].state = StepState.SKIPPED

                    # Start new step
                    step.state = StepState.RUNNING
                    step.start_time = datetime.now()
                    self.current_step_index = i
                    break

    def complete_step_with_result(
        self,
        step_name: str,
        state: StepState,
        warning_count: int = 0,
        critical_warning_count: int = 0,
        error_count: int = 0,
    ) -> None:
        """Complete a step with specific result state and counts."""
        with self._lock:
            for i, step in enumerate(self.steps):
                if step.name == step_name:
                    # First, complete any previous running step
                    if self.current_step_index >= 0 and self.current_step_index < i:
                        for j in range(self.current_step_index, i):
                            prev_step = self.steps[j]
                            if prev_step.state == StepState.RUNNING:
                                prev_step.state = StepState.COMPLETED
                                prev_step.end_time = datetime.now()
                            elif prev_step.state == StepState.PENDING:
                                prev_step.state = StepState.SKIPPED

                    # Now complete this step with the result
                    step.state = state
                    step.end_time = datetime.now()
                    step.warning_count = warning_count
                    step.critical_warning_count = critical_warning_count
                    step.error_count = error_count

                    # Accumulate to project totals
                    self.total_warnings += warning_count
                    self.total_critical_warnings += critical_warning_count
                    self.total_errors += error_count

                    self.current_step_index = i
                    break

    def mark_step_failed(self, step_name: str, error_count: int = 1) -> None:
        """Mark a specific step as failed without failing the whole project."""
        with self._lock:
            for i, step in enumerate(self.steps):
                if step.name == step_name:
                    step.state = StepState.FAILED
                    step.end_time = datetime.now()
                    step.error_count += error_count
                    self.total_errors += error_count
                    self.current_step_index = i
                    break

    def fail(self, message: Optional[str] = None) -> None:
        """Mark project as failed - thread-safe."""
        with self._lock:
            self.overall_state = StepState.FAILED
            self.message = message

            # Check if there are any steps that are still PENDING or RUNNING
            has_incomplete_steps = any(
                step.state in [StepState.PENDING, StepState.RUNNING]
                for step in self.steps
            )

            if not has_incomplete_steps:
                # All steps already completed - don't mark any as failed.
                # Happens when the process errored but every step still ran.
                return

            # Find the step to mark as failed:
            # - If current step is RUNNING, mark it as failed
            # - If current step is COMPLETED, mark the next pending step as failed
            failed_step_index = self.current_step_index

            if self.current_step_index >= 0:
                current_step = self.steps[self.current_step_index]
                if (
                    current_step.state == StepState.COMPLETED
                    or current_step.state == StepState.WARNING
                ):
                    # Current step completed; the failure is in the next step.
                    for i in range(self.current_step_index + 1, len(self.steps)):
                        if self.steps[i].state == StepState.PENDING:
                            failed_step_index = i
                            break
                    else:
                        # No pending steps - all completed, nothing to mark failed.
                        return

            # Mark the failed step
            if 0 <= failed_step_index < len(self.steps):
                step = self.steps[failed_step_index]
                if step.state in [StepState.PENDING, StepState.RUNNING]:
                    step.state = StepState.FAILED
                    step.end_time = datetime.now()
                    if step.start_time is None:
                        step.start_time = datetime.now()

            # Skip remaining steps after the failed one
            for i in range(failed_step_index + 1, len(self.steps)):
                if self.steps[i].state == StepState.PENDING:
                    self.steps[i].state = StepState.SKIPPED

    def complete(self, with_warnings: bool = False) -> None:
        """Mark project as completed - thread-safe.

        Warnings do not change the overall state to WARNING: a project with only
        warnings is COMPLETED (success). Only errors cause FAILED.
        """
        with self._lock:
            self.overall_state = StepState.COMPLETED

            # Complete current step if running
            if self.current_step_index >= 0:
                step = self.steps[self.current_step_index]
                if step.state == StepState.RUNNING:
                    step.state = StepState.COMPLETED
                    step.end_time = datetime.now()

            # Skip remaining steps
            for step in self.steps:
                if step.state == StepState.PENDING:
                    step.state = StepState.SKIPPED
