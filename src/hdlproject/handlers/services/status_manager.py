"""Service for managing the progress display lifecycle.

``StatusManager`` owns the progress sink for an operation. When a status display
should be shown (interactive TTY, not silenced) it builds a
:class:`~hdlproject.utils.rich_sink.RichLiveSink`; otherwise ``display`` is
``None`` and the execution core runs without progress rendering.

Thread Safety:
  ``RichLiveSink`` is created once before parallel execution begins. Each project
  thread only updates its own project's status, and the sink uses Rich's
  thread-safe ``Live`` rendering. Safe for concurrent use during parallel builds.
"""

from pathlib import Path
from typing import Optional

from hdlproject.utils.logging_manager import get_logger, should_show_status_display
from hdlproject.utils.rich_sink import RichLiveSink

logger = get_logger(__name__)


class StatusManager:
    """Owns the progress sink lifecycle for one operation.

    Method calls are delegated to the underlying sink (or skipped if ``display``
    is ``None``). Each thread updates only its own project's status.
    """

    def __init__(
        self,
        operation_name: str,
        operation_steps: list[str],
        project_names: list[str],
    ):
        """Args:
        operation_name: Name of the operation (build, open, etc.)
        operation_steps: List of step names for this operation.
        project_names: Projects being processed.
        """
        self.display: Optional[RichLiveSink] = None
        self.operation_steps = operation_steps

        if not should_show_status_display():
            logger.debug("Status display disabled; running without rendering")
            return

        try:
            title = f"{operation_name.title()} Operations"
            self.display = RichLiveSink(title=title)
            for project_name in project_names:
                self.display.add_project(project_name, operation_steps)
            logger.debug(f"Status display ready for {len(project_names)} project(s)")
        except Exception as e:
            logger.warning(f"Could not create status display: {e}")
            self.display = None

    def set_project_log_file(self, project_name: str, log_file: Path) -> None:
        """Set the log file path for a project."""
        if self.display:
            try:
                self.display.set_project_log_file(project_name, str(log_file))
            except Exception as e:
                logger.debug(f"Could not set log file for {project_name}: {e}")

    def start(self) -> None:
        """Start the live display."""
        if self.display:
            self.display.start_display()

    def start_project(self, project_name: str) -> None:
        """Begin tracking a project."""
        if self.display:
            self.display.start_project(project_name)

    def update_step(
        self,
        project_name: str,
        step: str,
        failed: bool = False,
        warning_count: int = 0,
        critical_warning_count: int = 0,
        error_count: int = 0,
        step_result: Optional[str] = None,
    ) -> None:
        """Update the current step for a project."""
        if self.display:
            self.display.update_project_step(
                project_name,
                step,
                failed=failed,
                warning_count=warning_count,
                critical_warning_count=critical_warning_count,
                error_count=error_count,
                step_result=step_result,
            )

    def complete_project(
        self,
        project_name: str,
        success: bool,
        message: Optional[str] = None,
    ) -> None:
        """Mark a project complete."""
        if self.display:
            self.display.complete_project(
                project_name,
                success=success,
                message=message,
            )

    def cleanup(self) -> None:
        """Stop the display and release resources."""
        if self.display:
            try:
                self.display.stop_display()
                logger.debug("Status display stopped")
            except Exception as e:
                logger.debug(f"Error stopping status display: {e}")
            finally:
                self.display = None
