"""Vivado build step state machine.

``StepTracker`` is the pure, UI-agnostic core of output processing. It consumes
``ParsedMessage`` objects (one per Vivado output line, in order) and drives a
``ProgressSink`` while accumulating the counts needed to decide whether the run
succeeded. ``VivadoOutputProcessor`` owns the threads, the subprocess and the log
file; everything about *what a line means* lives here.

The two kinds of step are handled differently, exactly as Vivado output demands:

- **TCL steps** (``[HDLPROJECT_STEP_*]`` markers emitted by our own TCL): the
  step's own marker carries the authoritative warning/error counts, and *regular*
  Vivado ERROR/WARNING lines seen while a TCL step is active are ignored (the TCL
  layer reports its own result). Only ``[HDLPROJECT_STEP_ERROR]`` fails the step.
- **Vivado phases** (synthesis, place, route, …): we count the ERROR / CRITICAL
  WARNING / WARNING lines that occur between the phase's start and complete
  markers, and roll those into the step result and operation totals.

A ``threading.Lock`` guards the mutable state so the processor's two reader
threads (stdout/stderr) can feed the tracker concurrently. Each public method
takes the lock once; private helpers assume it is held.
"""

import threading
from dataclasses import dataclass, field
from typing import Optional

from hdlproject.core.progress import ProgressSink
from hdlproject.utils.vivado_output_parser import (
    MessageType as ParsedMessageType,
)
from hdlproject.utils.vivado_output_parser import (
    ParsedMessage,
    StepResultType,
)


@dataclass
class BuildOutcome:
    """The verdict for a completed run, derived from the accumulated state."""

    success: bool
    error_lines: list[str] = field(default_factory=list)
    has_warnings: bool = False
    total_warnings: int = 0
    total_critical_warnings: int = 0
    total_errors: int = 0
    timing_failed: bool = False
    failure_message: Optional[str] = None


class StepTracker:
    """Serially-fed (lock-guarded) state machine for one project's output."""

    _STEP_RESULT_STR = {
        StepResultType.SUCCESS: "success",
        StepResultType.WARNING: "warning",
        StepResultType.ERROR: "error",
    }

    def __init__(self, project_name: str, operation: str, sink: Optional[ProgressSink],
                 project_logger):
        """Args:
        project_name: Project whose output this tracks.
        operation: Operation name (build, export, …) used in messages.
        sink: Progress sink to drive, or ``None`` to track silently.
        project_logger: Per-project logger for the human-readable summary.
        """
        self.project_name = project_name
        self.operation = operation
        self.sink = sink
        self.project_logger = project_logger

        self._lock = threading.Lock()

        # TCL step failures (only [HDLPROJECT_STEP_ERROR] lands here)
        self._tcl_step_errors: list[str] = []
        self._timing_failed = False
        self._has_step_warnings = False

        # Current step (Vivado phase) message counts
        self._current_step_name: Optional[str] = None
        self._current_step_is_tcl = False
        self._current_step_warnings = 0
        self._current_step_critical_warnings = 0
        self._current_step_errors = 0

        # Operation-wide totals
        self._total_warnings = 0
        self._total_critical_warnings = 0
        self._total_errors = 0

    # === Per-line entry point ===

    def process(self, parsed: ParsedMessage, raw_line: str) -> None:
        """Consume one parsed output line and update state + sink."""
        with self._lock:
            # Stream the raw line to interactive front-ends for ERROR/WARNING
            # lines (the batch sink ignores process_output). Done regardless of
            # step type, matching historic behaviour.
            if self.sink and parsed.type in (
                ParsedMessageType.ERROR,
                ParsedMessageType.CRITICAL_WARNING,
                ParsedMessageType.WARNING,
            ):
                self.sink.process_output(raw_line, self.project_name)

            self._handle_parsed_message(parsed)

    def _handle_parsed_message(self, parsed: ParsedMessage) -> None:
        """Dispatch a parsed message (lock held)."""
        # During TCL steps, regular Vivado errors/warnings are ignored; only the
        # HDLPROJECT_STEP_* markers count.
        in_tcl_step = self._current_step_is_tcl

        if parsed.type == ParsedMessageType.ERROR:
            if not in_tcl_step:
                self._current_step_errors += 1
                self._total_errors += 1
                self.project_logger.error(f"Vivado error: {parsed.message}")

        elif parsed.type == ParsedMessageType.CRITICAL_WARNING:
            if not in_tcl_step:
                self._current_step_critical_warnings += 1
                self._total_critical_warnings += 1
                self.project_logger.warning(f"Critical warning: {parsed.message}")

        elif parsed.type == ParsedMessageType.WARNING:
            if not in_tcl_step:
                self._current_step_warnings += 1
                self._total_warnings += 1
                # Individual warnings are not logged to avoid spam.

        elif parsed.type == ParsedMessageType.STEP_UPDATE:
            if parsed.step_name:
                self._handle_step_update(parsed)

        elif parsed.type == ParsedMessageType.PROJECT_CONTEXT:
            if parsed.project_context_name and self.sink:
                self.sink.set_project_context_name(
                    self.project_name, parsed.project_context_name
                )
                self.project_logger.info(
                    f"Project context: {parsed.project_context_name}"
                )

        elif parsed.type == ParsedMessageType.BUILD_ARTEFACTS:
            if parsed.build_artefacts_path and self.sink:
                self.sink.set_build_artefacts_path(
                    self.project_name, parsed.build_artefacts_path
                )
                self.project_logger.info(
                    f"Build artefacts: {parsed.build_artefacts_path}"
                )

        elif parsed.type == ParsedMessageType.TIMING_RESULT:
            self._handle_timing_result(parsed)

    # === Step handling (lock held) ===

    def _handle_step_update(self, parsed: ParsedMessage) -> None:
        if parsed.is_step_start:
            self._current_step_name = parsed.step_name
            self._current_step_is_tcl = parsed.is_tcl_step
            self._reset_step_counts()

            if self.sink:
                # guarded by dispatch in _handle_parsed_message
                assert parsed.step_name is not None
                self.sink.update_project_step(
                    self.project_name, parsed.step_name, failed=False
                )
            self.project_logger.info(f"Step started: {parsed.step_name}")

        elif parsed.step_result:
            self._complete_step(parsed)

    def _complete_step(self, parsed: ParsedMessage) -> None:
        # guarded by dispatch in _handle_parsed_message / caller's elif check
        assert parsed.step_name is not None
        assert parsed.step_result is not None
        vivado_warnings = self._current_step_warnings
        vivado_critical_warnings = self._current_step_critical_warnings
        vivado_errors = self._current_step_errors

        if parsed.is_tcl_step:
            # TCL step: trust the counts from the HDLPROJECT_STEP_* marker.
            total_warnings = parsed.warning_count
            total_critical_warnings = parsed.critical_warning_count
            total_errors = parsed.error_count
            self._total_warnings += total_warnings
            self._total_critical_warnings += total_critical_warnings
            self._total_errors += total_errors
        else:
            # Vivado phase: use the counts accumulated since the start marker.
            total_warnings = vivado_warnings
            total_critical_warnings = vivado_critical_warnings
            total_errors = vivado_errors

        self._reset_step_counts()
        self._current_step_name = None
        self._current_step_is_tcl = False

        result_str = self._STEP_RESULT_STR.get(parsed.step_result)

        # For Vivado phases, upgrade the result if Vivado reported issues.
        is_step_failure = parsed.is_failure
        if not parsed.is_tcl_step:
            if total_errors > 0 or parsed.is_failure:
                result_str = "error"
                is_step_failure = True
            elif total_warnings > 0 or total_critical_warnings > 0:
                if result_str == "success":
                    result_str = "warning"

        if (
            result_str == "warning"
            or total_warnings > 0
            or total_critical_warnings > 0
        ):
            self._has_step_warnings = True

        if total_warnings or total_critical_warnings or total_errors:
            self.project_logger.info(
                f"Step: {parsed.step_name} [{result_str}] "
                f"(W:{total_warnings} CW:{total_critical_warnings} E:{total_errors})"
            )
        else:
            self.project_logger.info(f"Step: {parsed.step_name} [{result_str}]")

        if self.sink:
            self.sink.update_project_step(
                self.project_name,
                parsed.step_name,
                failed=is_step_failure,
                warning_count=total_warnings,
                critical_warning_count=total_critical_warnings,
                error_count=total_errors,
                step_result=result_str,
            )

        # TCL step errors gate the final success verdict.
        if parsed.is_failure and parsed.is_tcl_step:
            self._tcl_step_errors.append(f"TCL step failed: {parsed.step_name}")

    def _handle_timing_result(self, parsed: ParsedMessage) -> None:
        timing_passed = parsed.timing_passed
        report_path = parsed.timing_report_path
        if timing_passed is None:
            return

        if not timing_passed:
            self._timing_failed = True
            self.project_logger.error("Timing: FAILED - timing violations detected")
        else:
            self.project_logger.info("Timing: PASSED")

        if report_path:
            self.project_logger.info(f"Timing report: {report_path}")

        if self.sink:
            self.sink.set_extra_info(
                self.project_name,
                key="timing",
                label="Timing",
                value="PASSED" if timing_passed else "FAILED",
                style="green" if timing_passed else "bold red",
                path=report_path,
            )

    # === Finalisation ===

    def finalise_incomplete_step(self, process_failed: bool) -> None:
        """Report a Vivado step that started but never emitted a completion
        marker (e.g. write_bitstream crashed mid-phase)."""
        with self._lock:
            if self._current_step_name is None:
                return

            if self._current_step_is_tcl:
                # TCL steps always complete via markers; reaching here is anomalous.
                self._current_step_name = None
                self._current_step_is_tcl = False
                return

            step_name = self._current_step_name
            warnings = self._current_step_warnings
            critical_warnings = self._current_step_critical_warnings
            errors = self._current_step_errors

            self._current_step_name = None
            self._current_step_is_tcl = False
            self._reset_step_counts()

            if process_failed or errors > 0:
                result_str, failed = "error", True
            elif warnings > 0 or critical_warnings > 0:
                result_str, failed = "warning", False
            else:
                result_str, failed = "success", False

            self.project_logger.info(
                f"Step: {step_name} [{result_str}] (incomplete) "
                f"(W:{warnings} CW:{critical_warnings} E:{errors})"
            )

            if self.sink:
                self.sink.update_project_step(
                    self.project_name,
                    step_name,
                    failed=failed,
                    warning_count=warnings,
                    critical_warning_count=critical_warnings,
                    error_count=errors,
                    step_result=result_str,
                )

    def build_outcome(self, exit_code: int) -> BuildOutcome:
        """Compute the final verdict. A run succeeds only with a zero exit code,
        no TCL step errors, no Vivado errors and no timing failure."""
        with self._lock:
            has_vivado_errors = self._total_errors > 0
            success = (
                exit_code == 0
                and not self._tcl_step_errors
                and not has_vivado_errors
                and not self._timing_failed
            )
            error_lines = list(self._tcl_step_errors)
            has_warnings = (
                self._has_step_warnings
                or self._total_warnings > 0
                or self._total_critical_warnings > 0
            )

            failure_message = None
            if not success:
                if error_lines:
                    failure_message = (
                        f"{self.operation} failed with "
                        f"{len(error_lines)} TCL step error(s)"
                    )
                elif self._timing_failed:
                    failure_message = f"{self.operation} failed - timing violations"
                elif has_vivado_errors:
                    failure_message = (
                        f"{self.operation} failed with "
                        f"{self._total_errors} Vivado error(s)"
                    )
                else:
                    failure_message = f"{self.operation} failed (exit code {exit_code})"

            return BuildOutcome(
                success=success,
                error_lines=error_lines,
                has_warnings=has_warnings,
                total_warnings=self._total_warnings,
                total_critical_warnings=self._total_critical_warnings,
                total_errors=self._total_errors,
                timing_failed=self._timing_failed,
                failure_message=failure_message,
            )

    def _reset_step_counts(self) -> None:
        self._current_step_warnings = 0
        self._current_step_critical_warnings = 0
        self._current_step_errors = 0
