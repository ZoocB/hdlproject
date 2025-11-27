# core/output_processor.py
"""Direct output processing for Vivado processes"""

import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, IO

from hdlproject.utils.logging_manager import get_logger, get_project_logger
from hdlproject.utils.vivado_output_parser import (
    VivadoOutputParser,
    MessageType as ParsedMessageType,
    StepResultType,
)
from hdlproject.utils.status_display import LiveStatusDisplay, MessageLevel, StepState

logger = get_logger(__name__)


class VivadoOutputProcessor:
    """Processes output from a single Vivado process with step result detection"""

    def __init__(
        self,
        project_name: str,
        operation: str,
        parser: VivadoOutputParser,
        status_display: Optional[LiveStatusDisplay],
        log_file_path: Path,
    ):
        """
        Initialise processor for a specific project.

        Args:
            project_name: Name of the project
            operation: Operation being performed (build, open, etc.)
            parser: Parser configured with operation-specific patterns
            status_display: Optional status display to update
            log_file_path: Path to write log output
        """
        self.project_name = project_name
        self.operation = operation
        self.parser = parser
        self.status_display = status_display
        self.log_file_path = log_file_path

        # TCL step failure tracking (only [HDLPROJECT_STEP_ERROR] causes failure)
        self._tcl_step_errors = []

        # Timing failure tracking
        self._timing_failed = False

        # Operation-level tracking
        self._has_step_warnings = False
        self._lock = threading.Lock()

        # Per-step Vivado message counting (for Vivado phases, not
        # hdlproject specific TCL steps)
        self._current_step_name: Optional[str] = None
        self._current_step_is_tcl: bool = False
        self._current_step_warnings = 0
        self._current_step_critical_warnings = 0
        self._current_step_errors = 0

        # Accumulated totals for the entire operation
        self._total_warnings = 0
        self._total_critical_warnings = 0
        self._total_errors = 0

        # Get project logger
        self.project_logger = get_project_logger(project_name)

        # Ensure log directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

    def _reset_step_counts(self) -> None:
        """Reset per-step Vivado message counts"""
        self._current_step_warnings = 0
        self._current_step_critical_warnings = 0
        self._current_step_errors = 0

    def _get_step_counts(self) -> tuple[int, int, int]:
        """Get current step warning, critical warning, and error counts"""
        return (
            self._current_step_warnings,
            self._current_step_critical_warnings,
            self._current_step_errors,
        )

    def process_output(self, process: subprocess.Popen) -> tuple[bool, list[str]]:
        """
        Process output from Vivado process.

        Returns:
            tuple of (success, error_lines)
        """
        # Start project in status display
        if self.status_display:
            self.status_display.start_project(self.project_name)

        # Open log file for writing
        with open(self.log_file_path, "a", buffering=1) as log_file:
            # Create threads for stdout and stderr
            stdout_thread = threading.Thread(
                target=self._process_stream, args=(process.stdout, log_file, "STDOUT")
            )
            stderr_thread = threading.Thread(
                target=self._process_stream, args=(process.stderr, log_file, "STDERR")
            )

            # Start processing
            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            exit_code = process.wait()

            # Wait for threads to finish processing remaining output
            stdout_thread.join()
            stderr_thread.join()

        # Finalize any incomplete Vivado step (step started but never completed)
        self._finalize_incomplete_step(exit_code != 0)

        # Determine success - TCL step errors, Vivado errors, timing failure,
        # or non-zero exit code cause failure
        with self._lock:
            # Check if there were Vivado errors during any step
            has_vivado_errors = self._total_errors > 0

            # Timing failure also causes build failure
            timing_failed = self._timing_failed

            success = (
                (exit_code == 0)
                and (len(self._tcl_step_errors) == 0)
                and not has_vivado_errors
                and not timing_failed
            )
            error_lines = self._tcl_step_errors.copy()
            has_warnings = (
                self._has_step_warnings
                or self._total_warnings > 0
                or self._total_critical_warnings > 0
            )

            # Create concise failure message if needed
            failure_msg = None
            if not success:
                if error_lines:
                    failure_msg = f"{self.operation} failed with {len(error_lines)} TCL step error(s)"
                elif timing_failed:
                    failure_msg = f"{self.operation} failed - timing violations"
                elif has_vivado_errors:
                    failure_msg = f"{self.operation} failed with {self._total_errors} Vivado error(s)"
                else:
                    failure_msg = f"{self.operation} failed (exit code {exit_code})"

        # Update final status
        if self.status_display:
            if success:
                self.status_display.complete_project(
                    self.project_name, success=True, message=None
                )
            else:
                self.status_display.complete_project(
                    self.project_name, success=False, message=failure_msg
                )

        # Log summary
        if success:
            if has_warnings:
                self.project_logger.info(
                    f"{self.operation} completed with warnings "
                    f"(W:{self._total_warnings} CW:{self._total_critical_warnings})"
                )
            else:
                self.project_logger.info(f"{self.operation} completed successfully")
        else:
            self.project_logger.error(
                f"{self.operation} failed "
                f"(W:{self._total_warnings} CW:{self._total_critical_warnings} E:{self._total_errors})"
            )
            if error_lines:
                self.project_logger.error(f"TCL step errors: {len(error_lines)}")

        return success, error_lines

    def _finalize_incomplete_step(self, process_failed: bool) -> None:
        """
        Finalise any incomplete Vivado step when process ends.

        If a Vivado step was started but never completed (e.g., write_bitstream failed),
        we need to report its accumulated counts to the status display.
        """
        with self._lock:
            if self._current_step_name is None:
                return

            if self._current_step_is_tcl:
                # TCL steps should always complete via HDLPROJECT_STEP_* markers
                # If we get here, something went wrong
                self._current_step_name = None
                self._current_step_is_tcl = False
                return

            # Vivado step that never completed - finalise it with accumulated counts
            step_name = self._current_step_name
            warnings = self._current_step_warnings
            critical_warnings = self._current_step_critical_warnings
            errors = self._current_step_errors

            # Reset step tracking
            self._current_step_name = None
            self._current_step_is_tcl = False
            self._reset_step_counts()

        # Determine result - if process failed or there were errors, mark as error
        if process_failed or errors > 0:
            result_str = "error"
            failed = True
        elif warnings > 0 or critical_warnings > 0:
            result_str = "warning"
            failed = False
        else:
            result_str = "success"
            failed = False

        # Log the incomplete step
        self.project_logger.info(
            f"Step: {step_name} [{result_str}] (incomplete) "
            f"(W:{warnings} CW:{critical_warnings} E:{errors})"
        )

        # Update status display
        if self.status_display:
            self.status_display.update_project_step(
                self.project_name,
                step_name,
                failed=failed,
                warning_count=warnings,
                critical_warning_count=critical_warnings,
                error_count=errors,
                step_result=result_str,
            )

    def _process_stream(
        self, stream: IO[str], log_file: IO[str], stream_name: str
    ) -> None:
        """Process a single stream (stdout or stderr)"""
        try:
            for line in stream:
                # Strip trailing newline
                line_content = line.rstrip("\n")

                # Write to log file with timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_file.write(f"[{timestamp}] [{stream_name}] {line_content}\n")

                # Parse line
                parsed = self.parser.parse_line(line_content)

                # Update status display
                if self.status_display:
                    self._update_status_display(parsed, line_content)

                # Handle different message types based on current step type
                self._handle_parsed_message(parsed, line_content)

        except Exception as e:
            logger.error(f"Error processing {stream_name} for {self.project_name}: {e}")

    def _handle_parsed_message(self, parsed, line_content: str) -> None:
        """Handle parsed message based on current step context"""

        # During TCL steps, we IGNORE regular Vivado errors/warnings
        # Only HDLPROJECT_STEP_* markers matter for TCL steps
        with self._lock:
            is_in_tcl_step = self._current_step_is_tcl

        if parsed.type == ParsedMessageType.ERROR:
            if not is_in_tcl_step:
                # Only count Vivado errors during non-TCL steps (Vivado phases)
                with self._lock:
                    self._current_step_errors += 1
                    self._total_errors += 1
                self.project_logger.error(f"Vivado error: {parsed.message}")

        elif parsed.type == ParsedMessageType.CRITICAL_WARNING:
            if not is_in_tcl_step:
                # Only count during Vivado phases
                with self._lock:
                    self._current_step_critical_warnings += 1
                    self._total_critical_warnings += 1
                self.project_logger.warning(f"Critical warning: {parsed.message}")

        elif parsed.type == ParsedMessageType.WARNING:
            if not is_in_tcl_step:
                # Only count during Vivado phases
                with self._lock:
                    self._current_step_warnings += 1
                    self._total_warnings += 1
                # Don't log all warnings to avoid spam

        elif parsed.type == ParsedMessageType.STEP_UPDATE:
            if parsed.step_name:
                self._handle_step_update(parsed)

        elif parsed.type == ParsedMessageType.PROJECT_CONTEXT:
            if parsed.project_context_name and self.status_display:
                self.status_display.set_project_context_name(
                    self.project_name, parsed.project_context_name
                )
                self.project_logger.info(
                    f"Project context: {parsed.project_context_name}"
                )

        elif parsed.type == ParsedMessageType.BUILD_ARTEFACTS:
            if parsed.build_artefacts_path and self.status_display:
                self.status_display.set_build_artefacts_path(
                    self.project_name, parsed.build_artefacts_path
                )
                self.project_logger.info(
                    f"Build artefacts: {parsed.build_artefacts_path}"
                )

        elif parsed.type == ParsedMessageType.TIMING_RESULT:
            self._handle_timing_result(parsed)

    def _handle_timing_result(self, parsed) -> None:
        """Handle timing result from parsed message"""
        timing_passed = parsed.timing_passed
        report_path = parsed.timing_report_path

        if timing_passed is None:
            return

        # Track timing failure
        with self._lock:
            if not timing_passed:
                self._timing_failed = True

        # Log result
        if timing_passed:
            self.project_logger.info("Timing: PASSED")
        else:
            self.project_logger.error("Timing: FAILED - timing violations detected")

        if report_path:
            self.project_logger.info(f"Timing report: {report_path}")

        # Update status display with extra info
        if self.status_display:
            if timing_passed:
                self.status_display.set_extra_info(
                    self.project_name,
                    key="timing",
                    label="Timing",
                    value="PASSED",
                    style="green",
                    path=report_path,
                )
            else:
                self.status_display.set_extra_info(
                    self.project_name,
                    key="timing",
                    label="Timing",
                    value="FAILED",
                    style="bold red",
                    path=report_path,
                )

    def _handle_step_update(self, parsed) -> None:
        """Handle step update from parsed message"""
        if parsed.is_step_start:
            # Step is starting
            with self._lock:
                self._current_step_name = parsed.step_name
                self._current_step_is_tcl = parsed.is_tcl_step
                self._reset_step_counts()

            if self.status_display:
                self.status_display.update_project_step(
                    self.project_name, parsed.step_name, failed=False
                )

            self.project_logger.info(f"Step started: {parsed.step_name}")

        elif parsed.step_result:
            # Step completed with result
            self._complete_step(parsed)

    def _complete_step(self, parsed) -> None:
        """Complete a step with its result"""
        with self._lock:
            # Get Vivado counts accumulated during this step
            vivado_warnings, vivado_critical_warnings, vivado_errors = (
                self._get_step_counts()
            )

            # For TCL steps, use the counts from the TCL output
            # For Vivado steps, use the Vivado counts we tracked
            if parsed.is_tcl_step:
                # TCL step - use counts from HDLPROJECT_STEP_* marker
                total_warnings = parsed.warning_count
                total_critical_warnings = parsed.critical_warning_count
                total_errors = parsed.error_count

                # Add these to operation totals
                self._total_warnings += total_warnings
                self._total_critical_warnings += total_critical_warnings
                self._total_errors += total_errors
            else:
                # Vivado step - use counts we accumulated
                total_warnings = vivado_warnings
                total_critical_warnings = vivado_critical_warnings
                total_errors = vivado_errors

            # Reset for next step
            self._reset_step_counts()
            self._current_step_name = None
            self._current_step_is_tcl = False

        # Determine result string for display
        result_map = {
            StepResultType.SUCCESS: "success",
            StepResultType.WARNING: "warning",
            StepResultType.ERROR: "error",
        }
        result_str = result_map.get(parsed.step_result, None)

        # For Vivado steps, upgrade result if Vivado found issues
        # Also check if this was a failure pattern match
        is_step_failure = parsed.is_failure
        if not parsed.is_tcl_step:
            if total_errors > 0 or parsed.is_failure:
                result_str = "error"
                is_step_failure = True
            elif total_warnings > 0 or total_critical_warnings > 0:
                if result_str == "success":
                    result_str = "warning"

        # Track step-level warnings
        if result_str == "warning" or total_warnings > 0 or total_critical_warnings > 0:
            with self._lock:
                self._has_step_warnings = True

        # Log step completion
        if total_warnings > 0 or total_critical_warnings > 0 or total_errors > 0:
            self.project_logger.info(
                f"Step: {parsed.step_name} [{result_str}] "
                f"(W:{total_warnings} CW:{total_critical_warnings} E:{total_errors})"
            )
        else:
            self.project_logger.info(f"Step: {parsed.step_name} [{result_str}]")

        # Update status display
        if self.status_display:
            # For TCL step errors, mark step as failed
            # For Vivado step errors, also mark as failed
            failed = is_step_failure

            self.status_display.update_project_step(
                self.project_name,
                parsed.step_name,
                failed=failed,
                warning_count=total_warnings,
                critical_warning_count=total_critical_warnings,
                error_count=total_errors,
                step_result=result_str,
            )

        # Track TCL step errors for final success determination
        if parsed.is_failure and parsed.is_tcl_step:
            with self._lock:
                self._tcl_step_errors.append(f"TCL step failed: {parsed.step_name}")

    def _update_status_display(self, parsed, line_content: str) -> None:
        """Update status display based on parsed output"""
        # Process output for message level detection (for display only)
        if parsed.type in [
            ParsedMessageType.ERROR,
            ParsedMessageType.CRITICAL_WARNING,
            ParsedMessageType.WARNING,
        ]:
            # Map to status display message levels
            level_mapping = {
                ParsedMessageType.ERROR: MessageLevel.ERROR,
                ParsedMessageType.CRITICAL_WARNING: MessageLevel.CRITICAL,
                ParsedMessageType.WARNING: MessageLevel.WARNING,
            }
            level = level_mapping.get(parsed.type, MessageLevel.INFO)
            self.status_display.process_output(line_content, self.project_name)
