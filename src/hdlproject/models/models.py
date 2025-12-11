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
    ```
    """

    invoke: str = Field(
        description="Command to start the shell (e.g., 'docker_tool vivado-2023.2')"
    )
    heredoc: bool = Field(
        default=False,
        description="Use heredoc/stdin mode. Commands passed via stdin with 'set -e'.",
    )


class VivadoExecutor(FlexibleModel):
    """Configuration for executing a specific Vivado version.

    Defines how to execute Vivado and related tools (like hdldepends) for a
    specific version. Supports both local installations and containerized
    environments.

    The execution flow is: [shell] → [setup] → [injected commands] → [executable]

    Example:
    ```yaml
    vivado_executors:
      # Local installation
      "2020.1":
        setup:
          - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"
        executable: "vivado"

      # Docker container with heredoc
      "2023.2":
        shell:
          invoke: "docker_tool vivado-2023.2"
          heredoc: true
        setup:
          - "source /opt/Xilinx/Vivado/2023.2/settings64.sh"
        executable: "vivado"

      # Local with extra environment setup
      "2021.1":
        setup:
          - "source /tools/Xilinx/Vivado/2021.1/settings64.sh"
          - "export XILINX_LOCAL_USER_DATA=no"
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
            "Use this for Docker or other containerized environments."
        ),
    )

    def build_command(
        self,
        executable_args: list[str],
        extra_commands: Optional[list[str]] = None,
    ) -> tuple[list[str], Optional[str]]:
        """Build the execution command.

        Args:
            executable_args: Arguments to pass to the executable
            extra_commands: Additional commands to run before executable (e.g., hdldepends)

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
            return [self.shell.invoke], stdin_content
        elif self.shell:
            # Custom shell without heredoc: use -c with && chaining
            command_chain = " && ".join(all_commands)
            return [self.shell.invoke, "-c", command_chain], None
        else:
            # Local bash: use && chaining
            command_chain = " && ".join(all_commands)
            return ["/bin/bash", "-c", command_chain], None

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

    vivado_executors:
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
    vivado_executors: dict[str, VivadoExecutor] = Field(
        default_factory=dict,
        description="Vivado execution configs keyed by version (e.g., '2020.1'). Overridable per-project.",
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

    def get_vivado_executor(self, version: str) -> Optional[VivadoExecutor]:
        """Get executor configuration for a specific Vivado version."""
        return self.vivado_executors.get(version)


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


class Generic(FlexibleModel):
    """HDL generic/parameter for top-level module.

    Example:
    ```yaml
    top_level_generics:
      DATA_WIDTH:
        type: integer
        value: 32
      ENABLE_DEBUG:
        type: std_logic
        value: '1'
      INIT_VECTOR:
        type: std_logic_vector
        width: 8
        value: "0xFF"
        format: hex
    ```
    """

    type: str = Field(
        description="VHDL type (e.g., integer, std_logic, std_logic_vector)."
    )
    value: Optional[Union[str, int, float, bool]] = Field(
        default=None,
        description="Value to assign. Type must be compatible with declared type.",
    )
    width: Optional[int] = Field(
        default=None,
        description="Bit width for vector types.",
    )
    format: Optional[str] = Field(
        default=None,
        description="Value format hint ('hex', 'bin', 'dec').",
    )


class ProjectInformation(FlexibleModel):
    """Core project identification and settings.

    Example:
    ```yaml
    project_information:
      project_name: my_project
      top_level_file_name: top_level
      device_info:
        part_name: xc7z020clg400-1
        board_name: Arty_Z7_20
      vivado_version:
        year: "2020"
        minor: "1"
    ```
    """

    project_name: str = Field(
        description="Vivado project name. Used for .xpr file and output naming."
    )
    top_level_file_name: str = Field(
        description="Top-level HDL module filename (without path or extension)."
    )
    device_info: DeviceInfo = Field(description="FPGA device and board configuration.")
    vivado_version: VivadoVersion = Field(
        description="Vivado version to use for this project."
    )
    top_level_generics: dict[str, Generic] = Field(
        default_factory=dict,
        description="Generic parameters for top-level module. Keys are generic names.",
    )


class Constraint(FlexibleModel):
    """Constraint file configuration.

    Example:
    ```yaml
    constraints:
      - file: timing.xdc
      - file: pins.xdc
        fileset: constrs_1
      - file: debug.xdc
        execution: implementation
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
        description="When applied: 'synthesis', 'implementation', or both if not specified.",
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
      - file: system.tcl
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
    """

    write_hw_platform: WriteHwPlatformOptions = Field(
        default_factory=WriteHwPlatformOptions,
        description="Options for hardware platform file (.xsa) generation.",
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
    vivado_executors: Optional[dict[str, VivadoExecutor]] = Field(
        default=None,
        description="Project-specific Vivado executors. Overrides global settings.",
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
    environment_setup: Optional[dict[str, str]] = Field(
        default=None,
        description="Pre-processing scripts. Keys: executor, Values: script path. Output KEY=VALUE lines added to env.",
    )
    hdlproject_config_version: Optional[str] = Field(
        default="4.0.0",
        description="Configuration schema version.",
    )

    def get_vivado_executor(self, global_config: GlobalConfiguration) -> VivadoExecutor:
        """Get Vivado executor (project -> global lookup).

        Args:
            global_config: Global configuration for executor lookup

        Returns:
            VivadoExecutor for the project's Vivado version

        Raises:
            ValueError: If no executor is configured for the required version
        """
        version_str = self.project_information.vivado_version.full_version

        # Check project-level first
        if self.vivado_executors and version_str in self.vivado_executors:
            return self.vivado_executors[version_str]

        # Check global config
        if (
            global_config.vivado_executors
            and version_str in global_config.vivado_executors
        ):
            return global_config.vivado_executors[version_str]

        # No fallback - must be explicitly configured
        available = []
        if self.vivado_executors:
            available.extend(self.vivado_executors.keys())
        if global_config.vivado_executors:
            available.extend(global_config.vivado_executors.keys())

        available_str = ", ".join(sorted(set(available))) if available else "none"
        raise ValueError(
            f"No vivado_executor configured for version '{version_str}'.\n"
            f"Available versions: {available_str}\n"
            f"Add to hdlproject_global_config.yaml or project config:\n"
            f"  vivado_executors:\n"
            f'    "{version_str}":\n'
            f"      setup:\n"
            f'        - "source /path/to/Vivado/{version_str}/settings64.sh"\n'
            f'      executable: "vivado"'
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
