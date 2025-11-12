# handlers/services/status_manager.py
"""Service for managing status display lifecycle"""

from typing import Optional
from pathlib import Path

from hdlproject.utils.status_display import LiveStatusDisplay, DisplayMode
from hdlproject.utils.logging_manager import should_show_status_display
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class StatusManager:
    """Manages status display lifecycle with simplified interface"""
    
    def __init__(self, operation_name: str, operation_steps: list[str], project_names: list[str]):
        """
        Initialise status manager.
        
        Args:
            operation_name: Name of the operation (build, open, etc.)
            operation_steps: list of step names for this operation
            project_names: list of project names being processed
        """
        self.display: Optional[LiveStatusDisplay] = None
        self.operation_steps = operation_steps
        
        # Create display (always create, mode determines behavior)
        display_mode = DisplayMode.INTERACTIVE if should_show_status_display() else DisplayMode.SILENT
        
        try:
            # Create display with title
            title = f"{operation_name.title()} Operations"
            self.display = LiveStatusDisplay(
                title=title,
                mode=display_mode
            )
            
            # Add all projects to display
            for project_name in project_names:
                self.display.add_project(project_name, operation_steps)
            
            logger.debug(f"Status display created for {len(project_names)} project(s)")
        except Exception as e:
            logger.warning(f"Could not create status display: {e}")
            self.display = None
    
    def set_project_log_file(self, project_name: str, log_file: Path) -> None:
        """Set log file path for a project"""
        if self.display:
            try:
                self.display.set_project_log_file(project_name, str(log_file))
            except Exception as e:
                logger.debug(f"Could not set log file for {project_name}: {e}")
    
    def start(self) -> None:
        """Start the live display"""
        if self.display:
            self.display.start_display()
    
    def start_project(self, project_name: str) -> None:
        """Begin tracking a project"""
        if self.display:
            self.display.start_project(project_name)
    
    def update_step(self, project_name: str, step: str, failed: bool = False) -> None:
        """Update current step for a project"""
        if self.display:
            self.display.update_project_step(project_name, step, failed=failed)
    
    def complete_project(self, project_name: str, success: bool, 
                        message: Optional[str] = None) -> None:
        """Mark project as complete"""
        if self.display:
            self.display.complete_project(project_name, success=success, message=message)
    
    def process_output_line(self, project_name: str, line: str) -> None:
        """Process a line of Vivado output for message detection"""
        if self.display:
            self.display.process_output(line, project_name)
    
    def cleanup(self) -> None:
        """Cleanup display resources"""
        if self.display:
            try:
                self.display.stop_display()
                logger.debug("Status display stopped")
            except Exception as e:
                logger.debug(f"Error stopping status display: {e}")
            finally:
                self.display = None