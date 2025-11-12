# handlers/services/vivado_executor.py
"""Service for executing Vivado processes"""

import os
import subprocess
from pathlib import Path
from dataclasses import dataclass

from hdlproject.handlers.base.context import ProjectContext
from hdlproject.core.output_processor import VivadoOutputProcessor
from hdlproject.utils.vivado_output_parser import VivadoOutputParser, StepPattern
from hdlproject.utils.resources import get_tcl_script
from hdlproject.utils.logging_manager import get_logger, get_project_logger

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of Vivado execution"""
    success: bool
    error_lines: list[str]
    exit_code: int = 0


class VivadoExecutor:
    """Handles all Vivado process execution"""
    
    def execute(self,
                project_context: ProjectContext,
                tcl_mode: str,
                step_patterns: list[StepPattern],
                status_display=None,
                cores: int = 1) -> ExecutionResult:
        """
        Execute Vivado for a project.
        
        Args:
            project_context: Project context with config and paths
            tcl_mode: TCL script mode (build, open, export, etc.)
            step_patterns: Patterns for parsing output
            status_display: Optional status display for updates
            cores: Number of CPU cores to use
            
        Returns:
            ExecutionResult with success status and errors
        """
        project_logger = get_project_logger(project_context.config.name)
        
        # Construct the command
        command = self._construct_command(project_context, tcl_mode, cores)
        
        # Create output parser
        parser = VivadoOutputParser(step_patterns)
        
        # Setup output processor
        log_path = project_context.operation_paths.get_log_file(tcl_mode)
        processor = VivadoOutputProcessor(
            project_name=project_context.config.name,
            operation=tcl_mode,
            parser=parser,
            status_display=status_display,
            log_file_path=log_path
        )
        
        # Execute process
        project_logger.info(f"Executing Vivado: {' '.join(command)}")
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=project_context.operation_paths.operation_dir,
                env=self._construct_environment(project_context)
            )
            
            # Process output
            success, error_lines = processor.process_output(process)
            
            return ExecutionResult(
                success=success,
                error_lines=error_lines,
                exit_code=process.returncode
            )
            
        except Exception as e:
            project_logger.error(f"Vivado execution failed: {e}")
            return ExecutionResult(
                success=False,
                error_lines=[str(e)],
                exit_code=-1
            )
    
    def execute_gui(self, project_path: Path, vivado_version) -> bool:
        """
        Open Vivado GUI with existing project.
        
        Args:
            project_path: Path to .xpr file
            vivado_version: VivadoVersion object
            
        Returns:
            True if successful
        """
        try:
            settings = str(vivado_version.settings_path)
            shell_cmd = f"source {settings} && vivado -mode gui -notrace {project_path}"
            
            process = subprocess.Popen(
                ["/bin/bash", "-c", shell_cmd],
                cwd=project_path.parent,
                env=os.environ.copy()
            )
            
            exit_code = process.wait()
            return exit_code == 0
            
        except Exception as e:
            logger.error(f"Failed to open GUI: {e}")
            return False
    
    def _construct_command(self, project_context: ProjectContext, 
                      tcl_mode: str, cores: int) -> list[str]:
        """Build Vivado command"""
        # Get TCL script
        tcl_script = get_tcl_script('project_workflow.tcl')
        
        # Get TCL arguments
        tcl_args = project_context.config.get_tcl_arguments(
            mode=tcl_mode,
            operation_paths=project_context.operation_paths,
            cores=cores
        )
        
        # Build command
        return [
            "vivado",
            "-mode", "batch",
            "-notrace",
            "-source", str(tcl_script),
            "-tclargs", *tcl_args
        ]
    
    def _construct_environment(self, project_context: ProjectContext) -> dict:
        """Construct the environment with Vivado settings sourced"""
        env = os.environ.copy()
        
        # Source Vivado settings
        settings = project_context.config.vivado_version.settings_path
        result = subprocess.run(
            ["/bin/bash", "-c", f"source {settings} && env"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse environment
        for line in result.stdout.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                env[key] = value
        
        return env