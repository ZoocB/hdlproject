"""Service for compile order generation.

This module provides a service for generating compile order files
using hdldepends. Supports both local execution and returning command
strings for Docker-based setups.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hdlproject.core.compile_order import CompileOrderManager
    from hdlproject.models.resolved import ResolvedProjectConfig, ResolvedOperationPaths

from hdlproject.utils.logging_manager import get_logger, get_project_logger

logger = get_logger(__name__)


class CompileOrderService:
    """Service for compile order generation.

    Handles compile order generation for operations that need it.
    Supports both direct execution (local setups) and command generation
    (Docker setups where hdldepends runs in the container).
    """

    def __init__(
        self,
        compile_manager: Optional["CompileOrderManager"],
        resolved_config: Optional["ResolvedProjectConfig"],
    ):
        """Initialise the service.

        Args:
            compile_manager: CompileOrderManager instance or None if not available
            resolved_config: ResolvedProjectConfig for accessing config (or None)
        """
        self.manager = compile_manager
        self.resolved_config = resolved_config

    def is_available(self) -> bool:
        """Check if compile order generation is available."""
        return self.manager is not None and self.resolved_config is not None

    def requires_shell_execution(self) -> bool:
        """Check if hdldepends must run in the executor's shell context.

        Returns True for Docker/custom shell setups where we can't capture
        environment variables locally.
        """
        if not self.resolved_config:
            return False

        return self.resolved_config.executor.shell is not None

    def prepare_for_operation(
        self, operation_paths: "ResolvedOperationPaths"
    ) -> None:
        """Prepare compile order for an operation.

        For local setups: generates compile order immediately.
        For Docker setups: logs that it will be done in shell context.

        Args:
            operation_paths: Paths for this operation
        """
        if not self.is_available():
            logger.debug("Compile order service not available")
            return

        project_logger = get_project_logger(self.resolved_config.project_name)

        if self.requires_shell_execution():
            project_logger.debug(
                "Compile order will be generated in shell context (Docker setup)"
            )
        else:
            self.generate(operation_paths)

    def get_extra_commands(
        self, operation_paths: "ResolvedOperationPaths"
    ) -> Optional[list[str]]:
        """Get extra commands to inject into shell execution.

        Returns hdldepends command for Docker setups, None otherwise.

        Args:
            operation_paths: Paths for this operation

        Returns:
            List with hdldepends command, or None
        """
        if not self.is_available() or not self.requires_shell_execution():
            return None

        hdldepends_cmd = self.get_command(operation_paths)
        if hdldepends_cmd:
            project_logger = get_project_logger(self.resolved_config.project_name)
            project_logger.debug(f"Adding hdldepends to shell: {hdldepends_cmd}")
            return [hdldepends_cmd]

        return None

    def get_command(
        self, operation_paths: "ResolvedOperationPaths"
    ) -> Optional[str]:
        """Get the hdldepends command string.

        Use this when hdldepends needs to run in the same shell context
        as Vivado (e.g., Docker containers).

        Args:
            operation_paths: Paths for this operation

        Returns:
            Command string for hdldepends, or None if not available
        """
        if not self.is_available():
            return None

        output_file = (
            operation_paths.operation_dir
            / f"compile_order.{self.manager.output_format}"
        )

        return self.manager.get_command(
            top_level_file=str(self.resolved_config.paths.top_level_file_path),
            output_file=output_file,
            tool_version=self.resolved_config.tool_version,
            device_part=self.resolved_config.device_part,
        )

    def generate(
        self, operation_paths: "ResolvedOperationPaths"
    ) -> Optional[Path]:
        """Generate compile order for the project (local execution).

        This executes hdldepends directly in a subprocess with environment
        variables captured from the Vivado setup commands. Only works for
        local setups (no custom shell).

        For Docker setups, use get_command() and pass it to the executor.

        Args:
            operation_paths: Paths for this operation

        Returns:
            Path to generated compile order file, or None if not generated
        """
        if not self.is_available():
            return None

        if self.requires_shell_execution():
            logger.debug("Compile order requires shell execution - use get_command()")
            return None

        project_logger = get_project_logger(self.resolved_config.project_name)

        try:
            tool_version = self.resolved_config.tool_version
            device_part = self.resolved_config.device_part

            project_logger.debug(
                f"Generating compile order with {self.resolved_config.tool} "
                f"{tool_version} and device {device_part}"
            )

            env = self._get_tool_environment()

            compile_order_path = self.manager.generate(
                root_dir=self.resolved_config.repository_root,
                top_level_file=str(self.resolved_config.paths.top_level_file_path),
                working_dir=operation_paths.operation_dir,
                tool_version=tool_version,
                device_part=device_part,
                env=env,
            )

            if compile_order_path:
                project_logger.info(f"Generated compile order: {compile_order_path}")
                return compile_order_path

            return None

        except Exception as e:
            project_logger.warning(f"Compile order generation failed: {e}")
            return None

    def _get_tool_environment(self) -> dict:
        """Get environment with tool settings.

        Note: Only called from generate() which already verified is_available().
        """
        env = os.environ.copy()

        executor = self.resolved_config.executor
        env_command = executor.get_environment_command()
        if not env_command:
            return env

        try:
            result = subprocess.run(
                ["/bin/bash", "-c", env_command],
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    env[key] = value

            logger.debug("Successfully set up tool environment")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to set up tool environment: {e}")

        return env
