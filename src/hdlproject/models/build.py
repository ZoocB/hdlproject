"""Build-time configuration models: constraints, sources, variables, hooks."""

from typing import Any, Optional, Union

from pydantic import Field

from hdlproject.models.base import FlexibleModel


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
        description=(
            "Target fileset (e.g., constrs_1). Defaults to main constraint fileset."
        ),
    )
    execution: Optional[str] = Field(
        default=None,
        description=(
            "Options: `immediate` - Executes the script immediate upon processing "
            "it and doesnt add it to the project."
        ),
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
        description=(
            "Shell command to execute. stdout is captured and stripped as the value."
        ),
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
      artefact_name: "{{ project_information.project_name | upper }}_v{{ \
build_variables.version_major }}"
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

    artefact_name: Optional[str] = Field(
        default=None,
        description=(
            "Jinja2 template string for the build artefact name. "
            "Rendered with the full resolved config and build variables as context. "
        ),
    )
    build_variables: dict[str, BuildVariable] = Field(
        default_factory=dict,
        description=(
            "Build-time variables resolved before synthesis. Keys are variable names."
        ),
    )
    generated_sources: list[GeneratedSource] = Field(
        default_factory=list,
        description=(
            "Jinja2 templates rendered at build time and added as project sources."
        ),
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
        description=(
            "Run after all project components (sources, constraints, IPs, BDs) "
            "are loaded."
        ),
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
