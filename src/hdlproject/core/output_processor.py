# core/output_processor.py
"""Direct output processing for Vivado processes"""

import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, IO

from hdlproject.utils.logging_manager import get_logger, get_project_logger
from hdlproject.utils.vivado_output_parser import (
    VivadoOutputParser, MessageType as ParsedMessageType
)
from hdlproject.utils.status_display import (
    LiveStatusDisplay, MessageLevel
)

logger = get_logger(__name__)


class VivadoOutputProcessor:
    """Processes output from a single Vivado process"""
    
    def __init__(self, 
                 project_name: str,
                 operation: str,
                 parser: VivadoOutputParser,
                 status_display: Optional[LiveStatusDisplay],
                 log_file_path: Path):
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
        self._error_lines = []
        self._critical_warning_count = 0
        self._warning_count = 0
        self._lock = threading.Lock()
        
        # Get project logger
        self.project_logger = get_project_logger(project_name)
        
        # Ensure log directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
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
        with open(self.log_file_path, 'a', buffering=1) as log_file:
            # Create threads for stdout and stderr
            stdout_thread = threading.Thread(
                target=self._process_stream,
                args=(process.stdout, log_file, "STDOUT")
            )
            stderr_thread = threading.Thread(
                target=self._process_stream,
                args=(process.stderr, log_file, "STDERR")
            )
            
            # Start processing
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            exit_code = process.wait()
            
            # Wait for threads to finish processing remaining output
            stdout_thread.join()
            stderr_thread.join()
        
        # Determine success
        with self._lock:
            success = (exit_code == 0) and (len(self._error_lines) == 0)
            error_lines = self._error_lines.copy()
            
            # Create concise failure message if needed
            failure_msg = None
            if not success:
                if error_lines:
                    # Just indicate failure type, not full error
                    failure_msg = f"{self.operation} failed with {len(error_lines)} error(s)"
                else:
                    failure_msg = f"{self.operation} failed (exit code {exit_code})"
        
        # Update final status
        if self.status_display:
            self.status_display.complete_project(
                self.project_name,
                success=success,
                message=failure_msg
            )
        
        # Log summary
        if success:
            self.project_logger.info(f"{self.operation} completed successfully")
        else:
            self.project_logger.error(f"{self.operation} failed")
            if error_lines:
                self.project_logger.error(f"Found {len(error_lines)} errors")
        
        return success, error_lines
    
    def _process_stream(self, stream: IO[str], log_file: IO[str], stream_name: str) -> None:
        """Process a single stream (stdout or stderr)"""
        try:
            for line in stream:
                # Strip trailing newline
                line_content = line.rstrip('\n')
                
                # Write to log file with timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_file.write(f"[{timestamp}] [{stream_name}] {line_content}\n")
                
                # Parse line
                parsed = self.parser.parse_line(line_content)
                
                # Update status display
                if self.status_display:
                    self._update_status_display(parsed, line_content)
                
                # Handle different message types
                if parsed.type == ParsedMessageType.ERROR:
                    with self._lock:
                        self._error_lines.append(parsed.message)
                    self.project_logger.error(f"Vivado error: {parsed.message}")
                    
                elif parsed.type == ParsedMessageType.CRITICAL_WARNING:
                    with self._lock:
                        self._critical_warning_count += 1
                    self.project_logger.warning(f"Critical warning: {parsed.message}")
                    
                elif parsed.type == ParsedMessageType.WARNING:
                    with self._lock:
                        self._warning_count += 1
                    # Don't log all warnings to avoid spam
                    
                elif parsed.type == ParsedMessageType.STEP_UPDATE:
                    if parsed.step_name:
                        self.project_logger.info(f"Step: {parsed.step_name}")
                        
        except Exception as e:
            logger.error(f"Error processing {stream_name} for {self.project_name}: {e}")
    
    def _update_status_display(self, parsed, line_content: str) -> None:
        """Update status display based on parsed output"""
        # Handle step updates
        if parsed.type == ParsedMessageType.STEP_UPDATE and parsed.step_name:
            self.status_display.update_project_step(
                self.project_name,
                parsed.step_name,
                failed=parsed.is_failure
            )
            if parsed.is_failure:
                with self._lock:
                    self._error_lines.append(f"Step failed: {parsed.step_name}")
        
        # Process output for message level detection
        elif parsed.type in [ParsedMessageType.ERROR, ParsedMessageType.CRITICAL_WARNING, ParsedMessageType.WARNING]:
            # Map to status display message levels
            level_mapping = {
                ParsedMessageType.ERROR: MessageLevel.ERROR,
                ParsedMessageType.CRITICAL_WARNING: MessageLevel.CRITICAL,
                ParsedMessageType.WARNING: MessageLevel.WARNING
            }
            level = level_mapping.get(parsed.type, MessageLevel.INFO)
            self.status_display.process_output(line_content, self.project_name)