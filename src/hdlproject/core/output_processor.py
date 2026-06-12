# core/output_processor.py
"""Streaming output processing for Vivado processes.

This is the IO/threading shell around :class:`StepTracker`. It reads the
process's stdout/stderr, timestamps every line into the log file, parses each
line, and feeds the parsed result to the tracker (which owns all interpretation
and sink updates). Success determination is delegated to the tracker's
``build_outcome``.
"""

import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import IO, Optional

from hdlproject.core.progress import ProgressSink
from hdlproject.core.step_tracker import StepTracker
from hdlproject.utils.logging_manager import get_logger, get_project_logger
from hdlproject.utils.vivado_output_parser import VivadoOutputParser

logger = get_logger(__name__)


class VivadoOutputProcessor:
    """Streams one Vivado process's output through a :class:`StepTracker`."""

    def __init__(
        self,
        project_name: str,
        operation: str,
        parser: VivadoOutputParser,
        status_display: Optional[ProgressSink],
        log_file_path: Path,
    ):
        """
        Args:
            project_name: Name of the project
            operation: Operation being performed (build, open, etc.)
            parser: Parser configured with operation-specific patterns
            status_display: Optional progress sink to update
            log_file_path: Path to write log output
        """
        self.project_name = project_name
        self.operation = operation
        self.parser = parser
        self.status_display = status_display
        self.log_file_path = log_file_path

        self.project_logger = get_project_logger(project_name)
        self.tracker = StepTracker(
            project_name=project_name,
            operation=operation,
            sink=status_display,
            project_logger=self.project_logger,
        )

        log_file_path.parent.mkdir(parents=True, exist_ok=True)

    def process_output(self, process: subprocess.Popen) -> tuple[bool, list[str]]:
        """Stream and interpret the process output.

        Returns:
            tuple of (success, error_lines)
        """
        if self.status_display:
            self.status_display.start_project(self.project_name)

        with open(self.log_file_path, "a", buffering=1) as log_file:
            stdout_thread = threading.Thread(
                target=self._process_stream, args=(process.stdout, log_file, "STDOUT")
            )
            stderr_thread = threading.Thread(
                target=self._process_stream, args=(process.stderr, log_file, "STDERR")
            )

            stdout_thread.start()
            stderr_thread.start()

            exit_code = process.wait()

            stdout_thread.join()
            stderr_thread.join()

        # Report any Vivado step that started but never completed.
        self.tracker.finalise_incomplete_step(exit_code != 0)

        outcome = self.tracker.build_outcome(exit_code)

        if self.status_display:
            self.status_display.complete_project(
                self.project_name,
                success=outcome.success,
                message=None if outcome.success else outcome.failure_message,
            )

        self._log_summary(outcome)
        return outcome.success, outcome.error_lines

    def _log_summary(self, outcome) -> None:
        """Write the human-readable per-project summary line(s)."""
        if outcome.success:
            if outcome.has_warnings:
                self.project_logger.info(
                    f"{self.operation} completed with warnings "
                    f"(W:{outcome.total_warnings} "
                    f"CW:{outcome.total_critical_warnings})"
                )
            else:
                self.project_logger.info(f"{self.operation} completed successfully")
        else:
            self.project_logger.error(
                f"{self.operation} failed "
                f"(W:{outcome.total_warnings} "
                f"CW:{outcome.total_critical_warnings} E:{outcome.total_errors})"
            )
            if outcome.error_lines:
                self.project_logger.error(
                    f"TCL step errors: {len(outcome.error_lines)}"
                )

    def _process_stream(
        self, stream: IO[str], log_file: IO[str], stream_name: str
    ) -> None:
        """Read one stream, log each line, and feed it to the tracker."""
        try:
            for line in stream:
                line_content = line.rstrip("\n")

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_file.write(f"[{timestamp}] [{stream_name}] {line_content}\n")

                parsed = self.parser.parse_line(line_content)
                self.tracker.process(parsed, line_content)

        except Exception as e:
            logger.error(f"Error processing {stream_name} for {self.project_name}: {e}")
