"""Service for executing EDA tool processes.

This module handles all tool process execution, using the ToolExecutor
configuration to properly set up the environment. Supports both local
installations and Docker-based execution.

Execution flow:
    [shell] -> [setup] -> [extra_commands (e.g., hdldepends)] -> [executable]
"""

import os
import shlex
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hdlproject.backends import get_tool_backend
from hdlproject.core.cancellation import CancellationToken, terminate_process_group
from hdlproject.core.output_processor import VivadoOutputProcessor
from hdlproject.core.progress import ProgressSink
from hdlproject.models.resolved import ResolvedOperationPaths, ResolvedProjectConfig
from hdlproject.utils.logging_manager import get_logger, get_project_logger
from hdlproject.utils.vivado_output_parser import StepPattern, VivadoOutputParser

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of Vivado execution."""

    success: bool
    error_lines: list[str]
    exit_code: int = 0
    cancelled: bool = False


class ToolExecutorService:
    """Service for executing EDA tool processes.

    Uses the ToolExecutor configuration from the ResolvedProjectConfig
    to properly set up the environment before running tool commands.
    Supports injecting additional commands (like hdldepends) that run
    before Vivado in the same shell session.
    """

    def _prepare_popen_args(
        self,
        shell_args: list[str],
        stdin_content: Optional[str],
    ) -> list[str]:
        """Prepare arguments for Popen based on execution mode."""
        if stdin_content:
            return shlex.split(shell_args[0])
        return shell_args

    def _handle_execution_failure(
        self,
        project_name: str,
        error_msg: str,
        log_path: Path,
        shell_args: list[str],
        stdin_content: Optional[str],
        status_display: Optional[ProgressSink],
        exit_code: int,
    ) -> ExecutionResult:
        """Handle execution failure with consistent logging and status updates."""
        project_logger = get_project_logger(project_name)
        project_logger.error(error_msg)

        self._write_error_to_log(log_path, error_msg, shell_args, stdin_content)

        if status_display:
            try:
                status_display.complete_project(
                    project_name,
                    success=False,
                    message=error_msg[:100],
                )
            except Exception:
                pass

        return ExecutionResult(
            success=False,
            error_lines=[error_msg],
            exit_code=exit_code,
        )

    def _start_cancel_watcher(
        self,
        process: subprocess.Popen,
        cancel_token: Optional[CancellationToken],
        project_logger,
    ) -> Optional[threading.Thread]:
        """Start a daemon thread that kills the process group on cancellation.

        Returns the thread (so the caller can join it), or ``None`` when there is
        no token to watch.
        """
        if cancel_token is None:
            return None

        def _watch() -> None:
            while process.poll() is None:
                if cancel_token.cancelled:
                    project_logger.warning(
                        "Cancellation requested - terminating Vivado process group"
                    )
                    terminate_process_group(process, project_logger)
                    return
                cancel_token.wait(0.2)

        watcher = threading.Thread(target=_watch, daemon=True)
        watcher.start()
        return watcher

    def execute(
        self,
        resolved_config: ResolvedProjectConfig,
        operation_paths: ResolvedOperationPaths,
        tcl_mode: str,
        step_patterns: list[StepPattern],
        status_display: Optional[ProgressSink] = None,
        cores: int = 1,
        extra_commands: Optional[list[str]] = None,
        build_steps: Optional[list[str]] = None,
        cancel_token: Optional[CancellationToken] = None,
    ) -> ExecutionResult:
        """Execute Vivado for a project.

        Args:
            resolved_config: Fully resolved project configuration
            operation_paths: Paths for this operation
            tcl_mode: TCL script mode (build, open, export, etc.)
            step_patterns: Patterns for parsing output
            status_display: Optional status display for updates
            cores: Number of CPU cores to use
            extra_commands: Additional commands to run before Vivado (e.g., hdldepends)
            build_steps: Build steps to run (only for build mode)
            cancel_token: Optional token; if cancelled, the Vivado process group
                is terminated and the result is marked ``cancelled``.

        Returns:
            ExecutionResult with success status and errors
        """
        project_logger = get_project_logger(resolved_config.project_name)

        executor = resolved_config.executor
        backend = get_tool_backend(resolved_config.tool)

        # Generate the tool's scripts and the entry-point invocation.
        entry_point = backend.generate_scripts(
            resolved_config=resolved_config,
            operation_paths=operation_paths,
            mode=tcl_mode,
            cores=cores,
            build_steps=build_steps,
        )
        tool_args = backend.batch_invocation(entry_point)

        # Build the complete command (handles heredoc vs && chaining)
        shell_args, stdin_content = executor.build_command(
            executable_args=tool_args,
            extra_commands=extra_commands,
            repository_root=resolved_config.repository_root,
        )

        # Create output parser
        parser = VivadoOutputParser(step_patterns)

        # Setup output processor
        log_path = operation_paths.get_log_file(tcl_mode)
        processor = VivadoOutputProcessor(
            project_name=resolved_config.project_name,
            operation=tcl_mode,
            parser=parser,
            status_display=status_display,
            log_file_path=log_path,
        )

        # Log what we're executing
        if stdin_content:
            project_logger.info(f"Executing via heredoc: {' '.join(shell_args)}")
            project_logger.debug(f"Script content:\n{stdin_content}")
        else:
            project_logger.info(f"Executing: {' '.join(shell_args)}")

        try:
            popen_args = self._prepare_popen_args(shell_args, stdin_content)

            process = subprocess.Popen(
                popen_args,
                stdin=subprocess.PIPE if stdin_content else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=operation_paths.operation_dir,
                env=os.environ.copy(),
                # New session so Vivado + its children form a killable group.
                start_new_session=True,
            )

            # If heredoc mode, write script to stdin
            if stdin_content:
                process.stdin.write(stdin_content)
                process.stdin.close()

            # Watch for cancellation and tear down the process group if requested.
            cancel_watcher = self._start_cancel_watcher(
                process, cancel_token, project_logger
            )

            # Process output - this handles streaming and logging
            success, error_lines = processor.process_output(process)

            # Wait for process to complete and get exit code
            process.wait()
            if cancel_watcher:
                cancel_watcher.join(timeout=1.0)

            if cancel_token and cancel_token.cancelled:
                project_logger.warning(f"{tcl_mode} cancelled by user")
                if status_display:
                    try:
                        status_display.complete_project(
                            resolved_config.project_name,
                            success=False,
                            message="Cancelled",
                        )
                    except Exception:
                        pass
                return ExecutionResult(
                    success=False,
                    error_lines=["Cancelled by user"],
                    exit_code=process.returncode,
                    cancelled=True,
                )

            # Check if process failed but processor didn't detect it
            if process.returncode != 0 and success:
                success = False
                if not error_lines:
                    try:
                        stderr_output = process.stderr.read()
                        if stderr_output:
                            error_lines = stderr_output.strip().splitlines()
                    except Exception:
                        pass
                if not error_lines:
                    error_lines = [f"Process exited with code {process.returncode}"]

                # Handle the undetected failure
                self._write_error_to_log(
                    log_path, "\n".join(error_lines), shell_args, stdin_content
                )
                if status_display:
                    try:
                        status_display.complete_project(
                            resolved_config.project_name,
                            success=False,
                            message=error_lines[0] if error_lines else "Unknown error",
                        )
                    except Exception:
                        pass

            return ExecutionResult(
                success=success,
                error_lines=error_lines,
                exit_code=process.returncode,
            )

        except FileNotFoundError as e:
            return self._handle_execution_failure(
                project_name=resolved_config.project_name,
                error_msg=f"Command not found: {e.filename}",
                log_path=log_path,
                shell_args=shell_args,
                stdin_content=stdin_content,
                status_display=status_display,
                exit_code=127,
            )

        except Exception as e:
            return self._handle_execution_failure(
                project_name=resolved_config.project_name,
                error_msg=f"Vivado execution failed: {e}",
                log_path=log_path,
                shell_args=shell_args,
                stdin_content=stdin_content,
                status_display=status_display,
                exit_code=-1,
            )

    def _write_error_to_log(
        self,
        log_path: Path,
        error_msg: str,
        shell_args: list[str],
        stdin_content: Optional[str],
    ) -> None:
        """Write error information to log file for debugging."""
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if log_path.exists() else "w"

            with open(log_path, mode) as f:
                f.write("\n" + "=" * 60 + "\n")
                f.write("EXECUTION FAILED\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Error: {error_msg}\n\n")
                f.write(f"Command: {' '.join(shell_args)}\n\n")

                if stdin_content:
                    f.write("Script content:\n")
                    f.write("-" * 40 + "\n")
                    f.write(stdin_content)
                    f.write("\n" + "-" * 40 + "\n")
        except Exception as e:
            logger.warning(f"Failed to write error log: {e}")

    def execute_gui(
        self,
        resolved_config: ResolvedProjectConfig,
        project_path: Path,
    ) -> bool:
        """Open Vivado GUI with existing project.

        Args:
            resolved_config: Fully resolved project configuration
            project_path: Path to .xpr file

        Returns:
            True if successful
        """
        try:
            executor = resolved_config.executor
            backend = get_tool_backend(resolved_config.tool)

            tool_args = backend.gui_invocation(project_path)

            shell_args, stdin_content = executor.build_command(
                executable_args=tool_args,
                repository_root=resolved_config.repository_root,
            )

            logger.info(f"Opening GUI: {' '.join(shell_args)}")
            popen_args = self._prepare_popen_args(shell_args, stdin_content)

            process = subprocess.Popen(
                popen_args,
                stdin=subprocess.PIPE if stdin_content else None,
                cwd=project_path.parent,
                env=os.environ.copy(),
            )

            if stdin_content:
                process.stdin.write(stdin_content)
                process.stdin.close()

            return process.wait() == 0

        except FileNotFoundError as e:
            logger.error(f"Command not found: {e.filename}")
            return False

        except Exception as e:
            logger.error(f"Failed to open GUI: {e}")
            return False
