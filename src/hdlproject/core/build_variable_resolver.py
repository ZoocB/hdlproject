"""Resolves build variables from static values or shell commands.

Each build variable is either a static value or a shell command whose
stdout is captured. Resolved variables are passed to Jinja2 templates
for generated source files and to the TCL template context.
"""

import subprocess
from pathlib import Path
from typing import Union

from hdlproject.models.models import BuildVariable
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class BuildVariableResolver:
    """Resolves build variables to their final values."""

    def resolve_all(
        self,
        variables: dict[str, BuildVariable],
        working_dir: Path,
    ) -> dict[str, Union[str, int, float]]:
        """Resolve all build variables.

        Args:
            variables: Build variable definitions from config
            working_dir: Working directory for command execution
                (typically the project directory where the YAML lives)

        Returns:
            Dict of variable name to resolved value
        """
        resolved = {}

        for name, var in variables.items():
            resolved[name] = self._resolve_one(name, var, working_dir)

        return resolved

    def _resolve_one(
        self,
        name: str,
        var: BuildVariable,
        working_dir: Path,
    ) -> Union[str, int, float]:
        """Resolve a single build variable.

        Args:
            name: Variable name (for logging)
            var: Variable definition
            working_dir: Working directory for command execution

        Returns:
            Resolved value

        Raises:
            ValueError: If neither value nor command is set, or command fails
        """
        if var.value is not None:
            logger.debug(f"Build variable '{name}' = {var.value!r} (static)")
            return var.value

        if var.command is not None:
            return self._execute_command(name, var.command, working_dir)

        raise ValueError(
            f"Build variable '{name}' has neither 'value' nor 'command' set."
        )

    def _execute_command(
        self,
        name: str,
        command: str,
        working_dir: Path,
    ) -> str:
        """Execute a shell command and capture stdout.

        Args:
            name: Variable name (for logging/errors)
            command: Shell command to execute
            working_dir: Working directory for execution

        Returns:
            Stripped stdout output

        Raises:
            ValueError: If command fails
        """
        logger.debug(f"Build variable '{name}': running '{command}'")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(
                f"Build variable '{name}': command timed out after 30s: {command}"
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise ValueError(
                f"Build variable '{name}': command failed (exit {result.returncode}): "
                f"{command}\n{stderr}"
            )

        value = result.stdout.strip()
        logger.debug(f"Build variable '{name}' = {value!r} (from command)")
        return value
