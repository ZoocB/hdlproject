"""
# YAML Configuration Guide

This document describes the structure and options for HDL project configuration files.

*Auto-generated from Pydantic models. Do not edit manually.*

## Configuration Files

There are two types of configuration files:

- **Global Configuration** (`hdlproject_global_config.yaml`): Located at repository root, defines repository-wide settings
- **Project Configuration** (`hdlproject_project_config.yaml`): Located in each project directory, defines project-specific settings

Project-level settings override global settings where noted.

## Inheritance

Configuration files support inheritance via the `inherits` key:

```yaml
inherits: base-config.yaml
# or multiple parents:
inherits:
  - base-config.yaml
  - device-config.yaml
```

**Merge behaviour:**

| Type | Behaviour |
|------|-----------|
| Lists | Appended (parent items first, then child items) |
| Dicts | Recursively merged |
| Scalars | Error if defined in both parent and child |
"""

from typing import Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
import os
import re
from pathlib import Path


class FlexibleModel(BaseModel):
    """Base model with environment variable substitution.

    All string values in configuration files support `${VAR}` syntax for
    environment variable expansion:

    ```yaml
    project_information:
      project_name: ${PROJECT_PREFIX}_design
    ```

    Variables are expanded at load time. If a variable is not set,
    the literal `${VAR}` string is preserved.
    """

    model_config = ConfigDict(
        extra="allow", validate_assignment=True, str_strip_whitespace=True
    )

    @field_validator("*", mode="before")
    @classmethod
    def substitute_env_vars(cls, v: Any) -> Any:
        """Replace ${VAR} with environment variable values."""
        if isinstance(v, str):
            return re.sub(
                r"\$\{([A-Z_][A-Z0-9_]*)\}",
                lambda m: os.environ.get(m.group(1), m.group(0)),
                v,
            )
        elif isinstance(v, dict):
            return {k: cls.substitute_env_vars(val) for k, val in v.items()}
        elif isinstance(v, list):
            return [cls.substitute_env_vars(item) for item in v]
        return v


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
            extra_commands: Additional commands to run before executable (e.g., hdldepends)
            repository_root: Repository root path (needed if shell.mount_repo_root is True)

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


# Backwards-compatible alias
VivadoExecutor = ToolExecutor


class GlobalConfiguration(FlexibleModel):
    """Global repository configuration (`hdlproject_global_config.yaml`).

    Located at repository root. Settings can be overridden at project level.

    Example:
    ```yaml
    project_dir: "fw/prj"
    hdldepends_config: "hdldepends.json"
    default_cores: 2
    max_parallel_builds: 4
    compile_order_format: "json"

    tools:
      vivado:
        "2020.1":
          setup:
            - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"
          executable: "vivado"
        "2023.2":
          shell:
            invoke: "docker_tool vivado-2023.2"
            heredoc: true
          setup:
            - "source /opt/Xilinx/Vivado/2023.2/settings64.sh"
          executable: "vivado"
    ```
    """

    project_dir: str = Field(
        description="Base directory containing project directories, relative to repository root."
    )
    hdldepends_config: Optional[str] = Field(
        default=None,
        description="Default hdldepends config path, relative to repository root. Overridable per-project.",
    )
    tools: dict[str, dict[str, ToolExecutor]] = Field(
        default_factory=dict,
        description=(
            "Tool execution configs keyed by tool name then version. "
            "e.g., tools.vivado.'2020.1'. Overridable per-project."
        ),
    )
    default_cores: int = Field(
        default=2,
        description="Default CPU cores per project for synthesis/implementation.",
    )
    max_parallel_builds: Optional[int] = Field(
        default=None,
        description="Maximum parallel builds. If None, calculated from system resources.",
    )
    compile_order_format: str = Field(
        default="json",
        description="Output format for compile order files ('json' or 'tcl').",
    )

    def get_tool_executor(self, tool: str, version: str) -> Optional[ToolExecutor]:
        """Get executor configuration for a specific tool and version."""
        tool_executors = self.tools.get(tool, {})
        return tool_executors.get(version)


class DeviceInfo(FlexibleModel):
    """FPGA device and board configuration.

    Example:
    ```yaml
    device_info:
      part_name: xc7z020clg400-1
      board_name: Arty_Z7_20
      board_part: digilentinc.com:arty-z7-20:part0:1.1
    ```
    """

    part_name: str = Field(
        description="Xilinx FPGA part number (e.g., xc7a35tcpg236-1)."
    )
    board_name: str = Field(description="Human-readable board name for identification.")
    board_part: Optional[str] = Field(
        default=None,
        description="Xilinx board part identifier (e.g., digilentinc.com:arty-a7-35:part0:1.1).",
    )


class ProjectInformation(FlexibleModel):
    """Core project identification and settings.

    Example:
    ```yaml
    project_information:
      project_name: my_project
      top_level_file_name: top_level
      tool: vivado
      tool_version: "2020.1"
      device_info:
        part_name: xc7z020clg400-1
        board_name: Arty_Z7_20
    ```
    """

    project_name: str = Field(
        description="Tool project name. Used for project file and output naming."
    )
    top_level_file_name: str = Field(
        description="Top-level HDL module filename (without path or extension)."
    )
    device_info: DeviceInfo = Field(description="FPGA device and board configuration.")
    tool: str = Field(
        default="vivado",
        description="EDA tool to use for this project (e.g., 'vivado').",
    )
    tool_version: str = Field(
        description="Tool version string (e.g., '2020.1').",
    )

    @property
    def tool_version_year(self) -> str:
        """Get the year/major component of the tool version (e.g., '2020' from '2020.1')."""
        return self.tool_version.split(".")[0]

    @property
    def tool_version_minor(self) -> str:
        """Get the minor component of the tool version (e.g., '1' from '2020.1')."""
        parts = self.tool_version.split(".")
        return parts[1] if len(parts) > 1 else "0"


class Constraint(FlexibleModel):
    """Constraint file configuration.

    Example:
    ```yaml
    constraints:
      - file: timing.xdc
      - file: pins.xdc
        fileset: constrs_1
      - file: debug.xdc
        execution: immediate
        properties:
          USED_IN_SYNTHESIS: false
    ```
    """

    file: str = Field(
        description="Path to constraint file (.xdc), relative to config file."
    )
    fileset: Optional[str] = Field(
        default=None,
        description="Target fileset (e.g., constrs_1). Defaults to main constraint fileset.",
    )
    execution: Optional[str] = Field(
        default=None,
        description="Options: `immediate` - Executes the script immediate upon processing it and doesnt add it to the project.",
    )
    properties: Optional[Union[list[dict[str, str]], dict[str, str]]] = Field(
        default=None,
        description="Additional Vivado properties for the constraint file.",
    )

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Ensure properties are in list format."""
        data = super().model_dump(**kwargs)
        if "properties" in data and isinstance(data["properties"], dict):
            data["properties"] = [data["properties"]]
        return data


class BlockDesign(FlexibleModel):
    """Block design configuration.

    Example:
    ```yaml
    block_designs:
      - file: processing_system.bd
        commands:
          - "regenerate_bd_layout"
          - "validate_bd_design"
    ```
    """

    file: str = Field(
        description="Path to block design file (.tcl or .bd), relative to config file."
    )
    commands: Optional[list[str]] = Field(
        default=None,
        description="Additional TCL commands to execute after loading.",
    )


class BuildVariable(FlexibleModel):
    """A build-time variable resolved before synthesis.

    Use `value` for static data or `command` for dynamically computed data.
    Exactly one of `value` or `command` must be set.

    Example:
    ```yaml
    build_variables:
      version_major:
        value: 1
      git_hash:
        command: "git rev-parse --short HEAD"
      build_date:
        command: "date +%y%m%d"
    ```
    """

    value: Optional[Union[str, int, float]] = Field(
        default=None,
        description="Static value for this variable.",
    )
    command: Optional[str] = Field(
        default=None,
        description="Shell command to execute. stdout is captured and stripped as the value.",
    )


class GeneratedSource(FlexibleModel):
    """A Jinja2 template that is rendered at build time and added to the project.

    The template has access to the full resolved project configuration
    and resolved build variables. Reference values explicitly:
    - ``{{ build_variables.version_major }}``
    - ``{{ project_information.project_name }}``
    - ``{{ project_information.device_info.board_name }}``

    Example:
    ```yaml
    generated_sources:
      - template: "hdl/build_info_pkg.vhd.j2"
    ```
    """

    template: str = Field(
        description="Path to Jinja2 template file, relative to the YAML config file.",
    )


class WriteHwPlatformOptions(FlexibleModel):
    """Options for write_hw_platform Vivado command.

    Example:
    ```yaml
    build_configuration:
      write_hw_platform:
        include_bit: true
    ```
    """

    include_bit: bool = Field(
        default=False,
        description="Include bitstream in hardware platform file (.xsa).",
    )


class BuildConfiguration(FlexibleModel):
    """Build-time configuration for synthesis and implementation.

    These are persistent options stored in the config, distinct from
    CLI runtime options like --cores or --clean.

    Example:
    ```yaml
    build_configuration:
      build_variables:
        version_major:
          value: 1
        version_minor:
          value: 0
        git_hash:
          command: "git rev-parse --short HEAD"
      generated_sources:
        - template: "hdl/build_info_pkg.vhd.j2"
      write_hw_platform:
        include_bit: true
    ```
    """

    build_variables: dict[str, BuildVariable] = Field(
        default_factory=dict,
        description="Build-time variables resolved before synthesis. Keys are variable names.",
    )
    generated_sources: list[GeneratedSource] = Field(
        default_factory=list,
        description="Jinja2 templates rendered at build time and added as project sources.",
    )
    write_hw_platform: WriteHwPlatformOptions = Field(
        default_factory=WriteHwPlatformOptions,
        description="Options for hardware platform file (.xsa) generation.",
    )


class HooksConfig(FlexibleModel):
    """TCL hook points for injecting custom commands at lifecycle stages.

    Each hook is a list of TCL commands executed at that point in the workflow.
    Hooks run inside the Vivado TCL interpreter and have access to the full
    Vivado command set plus all project context variables.

    Example:
    ```yaml
    hooks:
      post_project_create:
        - "set_property IP_REPO_PATHS /path/to/custom_ips [current_project]"
        - "update_ip_catalog"
      pre_synthesis:
        - 'source "$env(REPO_ROOT)/scripts/pre_synth_checks.tcl"'
      post_implementation:
        - "report_utilization -file utilization.rpt"
      post_bitstream:
        - 'source "$env(REPO_ROOT)/scripts/post_build.tcl"'
    ```
    """

    post_project_create: list[str] = Field(
        default_factory=list,
        description="Run after project creation and standard property setup.",
    )
    post_project_setup: list[str] = Field(
        default_factory=list,
        description="Run after all project components (sources, constraints, IPs, BDs) are loaded.",
    )
    pre_build: list[str] = Field(
        default_factory=list,
        description="Run before the build flow starts (before synthesis).",
    )
    pre_synthesis: list[str] = Field(
        default_factory=list,
        description="Run immediately before synthesis launch.",
    )
    post_synthesis: list[str] = Field(
        default_factory=list,
        description="Run after synthesis completes successfully.",
    )
    pre_implementation: list[str] = Field(
        default_factory=list,
        description="Run immediately before implementation launch.",
    )
    post_implementation: list[str] = Field(
        default_factory=list,
        description="Run after implementation completes successfully.",
    )
    post_bitstream: list[str] = Field(
        default_factory=list,
        description="Run after bitstream generation and artefact packaging.",
    )


class ProjectConfiguration(FlexibleModel):
    """Root project configuration (`hdlproject_project_config.yaml`).

    Located in each project directory. This is the top-level model representing
    a complete project configuration file.

    Example for `synth_options` and `impl_options` - these map directly to
    Vivado `set_property` commands:

    ```yaml
    synth_options:
      STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY: rebuilt
      STEPS.SYNTH_DESIGN.ARGS.DIRECTIVE: AreaOptimized_high

    impl_options:
      STEPS.OPT_DESIGN.ARGS.DIRECTIVE: Explore
      STEPS.PLACE_DESIGN.ARGS.DIRECTIVE: ExtraNetDelay_high
    ```

    Each generates TCL like:
    ```tcl
    set_property -name STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY -value rebuilt -objects [get_runs synth_1]
    ```
    """

    project_information: ProjectInformation = Field(
        description="Core project identification and settings."
    )
    hdldepends_config: Optional[str] = Field(
        default=None,
        description="Project-specific hdldepends config path. Overrides global setting.",
    )
    tools: Optional[dict[str, dict[str, ToolExecutor]]] = Field(
        default=None,
        description=(
            "Project-specific tool executors. Overrides global settings. "
            "Keyed by tool name then version."
        ),
    )
    constraints: list[Constraint] = Field(
        default_factory=list,
        description="Constraint files to include.",
    )
    block_designs: list[BlockDesign] = Field(
        default_factory=list,
        description="Block designs to include.",
    )
    synth_options: dict[str, str] = Field(
        default_factory=dict,
        description="Vivado synthesis properties (STEPS.SYNTH_DESIGN.ARGS.*).",
    )
    impl_options: dict[str, str] = Field(
        default_factory=dict,
        description="Vivado implementation properties (STEPS.*.ARGS.*).",
    )
    build_configuration: BuildConfiguration = Field(
        default_factory=BuildConfiguration,
        description="Build-time configuration options.",
    )
    hooks: HooksConfig = Field(
        default_factory=HooksConfig,
        description="TCL hook points for injecting custom commands at workflow lifecycle stages.",
    )
    environment_setup: Optional[dict[str, str]] = Field(
        default=None,
        description="Pre-processing scripts. Keys: executor, Values: script path. Output KEY=VALUE lines added to env.",
    )
    hdlproject_config_version: Optional[str] = Field(
        default="4.0.0",
        description="Configuration schema version.",
    )

    def get_tool_executor(self, global_config: GlobalConfiguration) -> ToolExecutor:
        """Get tool executor (project -> global lookup).

        Looks up the executor for the project's tool and version, checking
        project-level tools first, then falling back to global tools.

        Args:
            global_config: Global configuration for executor lookup

        Returns:
            ToolExecutor for the project's tool and version

        Raises:
            ValueError: If no executor is configured for the required tool/version
        """
        tool = self.project_information.tool
        version_str = self.project_information.tool_version

        # Check project-level first
        if self.tools:
            tool_executors = self.tools.get(tool, {})
            if version_str in tool_executors:
                return tool_executors[version_str]

        # Check global config
        global_executor = global_config.get_tool_executor(tool, version_str)
        if global_executor:
            return global_executor

        # No fallback - must be explicitly configured
        available = []
        if self.tools and tool in self.tools:
            available.extend(
                f"{tool}/{v}" for v in self.tools[tool].keys()
            )
        if tool in global_config.tools:
            available.extend(
                f"{tool}/{v}" for v in global_config.tools[tool].keys()
            )

        available_str = ", ".join(sorted(set(available))) if available else "none"
        raise ValueError(
            f"No executor configured for {tool} version '{version_str}'.\n"
            f"Available: {available_str}\n"
            f"Add to hdlproject_global_config.yaml or project config:\n"
            f"  tools:\n"
            f"    {tool}:\n"
            f'      "{version_str}":\n'
            f"        setup:\n"
            f'          - "source /path/to/{tool}/{version_str}/settings64.sh"\n'
            f'        executable: "{tool}"'
        )

    def get_hdldepends_config(
        self, global_config: GlobalConfiguration
    ) -> Optional[str]:
        """Get hdldepends config (project -> global fallback)."""
        return self.hdldepends_config or global_config.hdldepends_config

    def to_json_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(exclude_unset=True, exclude_none=True)

    def to_json(self, **kwargs) -> str:
        """Convert to JSON string."""
        import json

        return json.dumps(self.to_json_dict(), **kwargs)
