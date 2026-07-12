"""Tool-execution configuration models (Vivado version, shell, executor)."""

from pathlib import Path
from typing import Any, Optional

from pydantic import Field

from hdlproject.models.base import FlexibleModel


class VivadoVersion(FlexibleModel):
    """Vivado version specification.

    Example:
    ```yaml
    vivado_version:
      year: "2020"
      minor: "1"
    ```
    """

    year: str = Field(description="Vivado version year (e.g., '2020', '2023').")
    minor: str = Field(description="Vivado version minor release (e.g., '1', '2').")

    @property
    def full_version(self) -> str:
        """Get full version string (e.g., '2020.1')."""
        return f"{self.year}.{self.minor}"

    def __str__(self) -> str:
        return self.full_version

    def __hash__(self) -> int:
        return hash(self.full_version)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, VivadoVersion):
            return self.full_version == other.full_version
        return False


class ShellConfig(FlexibleModel):
    """Shell configuration for custom execution environments.

    Used when commands need to run in a custom shell (e.g., Docker container).
    When `heredoc` is true, commands are passed via stdin with `set -e` for
    error handling.

    Example:
    ```yaml
    shell:
      invoke: "docker_tool vivado-2023.2"
      heredoc: true
      mount_repo_root: true
      options:
        - "--pull=never"
    ```
    """

    invoke: str = Field(
        description="Command to start the shell (e.g., 'docker_tool vivado-2023.2')"
    )
    heredoc: bool = Field(
        default=False,
        description="Use heredoc/stdin mode. Commands passed via stdin with 'set -e'.",
    )
    mount_repo_root: bool = Field(
        default=False,
        description=(
            "Mount repository root into container. "
            "Adds '--volume {repo_root}:{repo_root}' to options."
        ),
    )
    options: list[str] = Field(
        default_factory=list,
        description=(
            "Additional options passed to the shell command after '--'. "
            "For docker_tool: docker/podman options like '--pull=never'."
        ),
    )


class ToolExecutor(FlexibleModel):
    """Configuration for executing a specific tool version.

    Defines how to execute a tool (e.g., Vivado) and related utilities
    (like hdldepends) for a specific version. Supports both local
    installations and containerised environments.

    The execution flow is: [shell] → [setup] → [injected commands] → [executable]

    Example:
    ```yaml
    tools:
      vivado:
        # Local installation
        "2020.1":
          setup:
            - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"
          executable: "vivado"

        # Docker container with heredoc and repo mounting
        "2023.2":
          shell:
            invoke: "docker_tool vivado-2023.2"
            heredoc: true
            mount_repo_root: true
            options:
              - "--pull=never"
          setup:
            - "source /opt/Xilinx/Vivado/2023.2/settings64.sh"
            - 'REPO_ROOT="$(git rev-parse --show-toplevel)"'
            - 'source "${REPO_ROOT}/venv/bin/activate"'
          executable: "vivado"
    ```
    """

    executable: str = Field(description="Command to invoke the tool (e.g., 'vivado')")
    setup: list[str] = Field(
        default_factory=list,
        description=(
            "Setup commands to run first (e.g., source settings.sh). "
            "Executed before any injected commands like hdldepends."
        ),
    )
    shell: Optional[ShellConfig] = Field(
        default=None,
        description=(
            "Custom shell configuration. If not set, uses /bin/bash with && chaining. "
            "Use this for Docker or other containerised environments."
        ),
    )

    def build_command(
        self,
        executable_args: list[str],
        extra_commands: Optional[list[str]] = None,
        repository_root: Optional[Path] = None,
    ) -> tuple[list[str], Optional[str]]:
        """Build the execution command.

        Args:
            executable_args: Arguments to pass to the executable
            extra_commands: Additional commands to run before executable
                (e.g., hdldepends)
            repository_root: Repository root path (needed if
                shell.mount_repo_root is True)

        Returns:
            Tuple of (shell_args, stdin_content):
            - shell_args: Command line arguments for subprocess
            - stdin_content: Content to pass via stdin (only for heredoc mode), or None
        """
        # Build the executable command with args
        exec_cmd = f"{self.executable} {' '.join(executable_args)}"

        # Combine all commands: setup + extra + executable
        all_commands = list(self.setup)
        if extra_commands:
            all_commands.extend(extra_commands)
        all_commands.append(exec_cmd)

        if self.shell and self.shell.heredoc:
            # Heredoc mode: pass commands via stdin
            script_lines = ["set -e"] + all_commands
            stdin_content = "\n".join(script_lines)

            # Build invoke command with options
            invoke_cmd = self._build_shell_invoke(repository_root)
            return [invoke_cmd], stdin_content
        elif self.shell:
            # Custom shell without heredoc: use -c with && chaining
            command_chain = " && ".join(all_commands)
            invoke_cmd = self._build_shell_invoke(repository_root)
            return [invoke_cmd, "-c", command_chain], None
        else:
            # Local bash: use && chaining
            command_chain = " && ".join(all_commands)
            return ["/bin/bash", "-c", command_chain], None

    def _build_shell_invoke(self, repository_root: Optional[Path] = None) -> str:
        """Build the shell invocation command with options.

        Args:
            repository_root: Repository root path for mount_repo_root option

        Returns:
            Complete shell invoke command string
        """
        if not self.shell:
            return "/bin/bash"

        parts = [self.shell.invoke]

        # Collect all options
        all_options = list(self.shell.options)

        # Add repo root mount if requested
        if self.shell.mount_repo_root:
            if repository_root:
                all_options.append(f"--volume {repository_root}:{repository_root}")
            else:
                # Log warning but don't fail - repository_root might not be available
                pass

        # Add options after '--' separator
        if all_options:
            parts.append("--")
            parts.extend(all_options)

        return " ".join(parts)

    def get_environment_command(self) -> Optional[str]:
        """Get command to capture environment variables.

        Only works for local (non-Docker) setups where we can capture
        the environment after running setup commands.

        Returns:
            Shell command string to run and capture env, or None if not applicable
        """
        if self.shell:
            # Can't capture environment from Docker/custom shells
            return None
        if not self.setup:
            return None

        # Build command that runs setup and prints environment
        setup_chain = " && ".join(self.setup)
        return f"{setup_chain} && env"
