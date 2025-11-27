"""Pydantic models for HDL project configuration.

These models define the structure and validation for YAML configuration files.
Documentation is auto-generated from these models - update Field descriptions here.
"""

from typing import Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
import os
import re


class FlexibleModel(BaseModel):
    """Base model that allows extra fields and performs environment variable substitution.

    All string values support ${VAR} syntax for environment variable expansion.
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


class DeviceInfo(FlexibleModel):
    """FPGA device and board configuration."""

    part_name: str = Field(
        description="Xilinx FPGA part number. Must be a valid Xilinx part (e.g., xc7a35tcpg236-1, xczu9eg-ffvb1156-2-e)."
    )
    board_name: str = Field(
        description="Human-readable board name for identification purposes."
    )
    board_part: Optional[str] = Field(
        default=None,
        description="Xilinx board part identifier. Must be a valid Xilinx board part if specified (e.g., digilentinc.com:arty-a7-35:part0:1.1).",
    )
    vivado_version_year: Optional[str] = Field(
        default=None,
        description="Vivado version year (e.g., 2023). Can be specified here or at project level.",
    )
    vivado_version_sub: Optional[str] = Field(
        default=None,
        description="Vivado version sub-release (e.g., 1, 2). Can be specified here or at project level.",
    )


class Generic(FlexibleModel):
    """HDL generic/parameter definition for top-level module."""

    type: str = Field(
        description="VHDL type of the generic (e.g., integer, std_logic, std_logic_vector)."
    )
    value: Optional[Union[str, int, float, bool]] = Field(
        default=None,
        description="Value to assign to the generic. Type must be compatible with the declared type.",
    )


class Constraint(FlexibleModel):
    """Constraint file configuration."""

    file: str = Field(
        description="Path to the constraint file (.xdc), relative to the configuration file location."
    )
    fileset: Optional[str] = Field(
        default=None,
        description="Target fileset for the constraint (e.g., constrs_1). Defaults to the project's main constraint fileset.",
    )
    execution: Optional[str] = Field(
        default=None,
        description="When the constraint should be applied: 'synthesis', 'implementation', or both if not specified.",
    )
    properties: Optional[Union[list[dict[str, str]], dict[str, str]]] = Field(
        default=None,
        description="Additional Vivado properties to set on the constraint file. Can be a single dict or list of dicts with property name-value pairs.",
    )

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override to ensure properties are in the right format."""
        data = super().model_dump(**kwargs)
        if "properties" in data and isinstance(data["properties"], dict):
            data["properties"] = [data["properties"]]
        return data


class BlockDesign(FlexibleModel):
    """Block design configuration."""

    file: str = Field(
        description="Path to the block design file (.tcl or .bd), relative to the configuration file location."
    )
    commands: Optional[list[str]] = Field(
        default=None,
        description="Additional TCL commands to execute after loading the block design.",
    )


class ProjectInformation(FlexibleModel):
    """Core project identification and settings."""

    project_name: str = Field(
        description="Name of the Vivado project. Used for project directory and output file naming."
    )
    top_level_file_name: str = Field(
        description="Filename of the top-level HDL module (without path). Must exist in the source file list."
    )
    device_info: DeviceInfo = Field(description="FPGA device and board configuration.")
    top_level_generics: dict[str, Generic] = Field(
        default_factory=dict,
        description="Generic parameters to pass to the top-level module. Keys are generic names, values are Generic objects.",
    )
    vivado_version_year: Optional[str] = Field(
        default=None,
        description="Vivado version year. Overrides device_info.vivado_version_year if both are specified.",
    )
    vivado_version_sub: Optional[str] = Field(
        default=None,
        description="Vivado version sub-release. Overrides device_info.vivado_version_sub if both are specified.",
    )

    def get_vivado_version(self) -> tuple[str, str]:
        """Get Vivado version from either location.

        Returns:
            Tuple of (year, sub-release)

        Raises:
            ValueError: If Vivado version is not specified in either location.
        """
        year = self.vivado_version_year or self.device_info.vivado_version_year
        sub = self.vivado_version_sub or self.device_info.vivado_version_sub

        if not year or not sub:
            raise ValueError("Vivado version not specified")

        return year, sub


class ProjectConfiguration(FlexibleModel):
    """Root configuration model for HDL projects.

    This is the top-level model that represents a complete project configuration file.
    Supports inheritance via the 'inherits' key (processed before model validation).
    """

    project_information: ProjectInformation = Field(
        description="Core project identification and settings. Required."
    )
    hdldepends_config: Optional[str] = Field(
        default=None,
        description="Path to hdldepends configuration file, relative to the project directory. Overrides default dependency resolution settings.",
    )
    constraints: list[Constraint] = Field(
        default_factory=list,
        description="List of constraint files to include in the project.",
    )
    block_designs: list[BlockDesign] = Field(
        default_factory=list,
        description="List of block designs to include in the project.",
    )
    synth_options: dict[str, str] = Field(
        default_factory=dict,
        description="Vivado synthesis options. Keys are property names (e.g., STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY), values are property values. Maps to set_property -name <key> -value <value>.",
    )
    impl_options: dict[str, str] = Field(
        default_factory=dict,
        description="Vivado implementation options. Keys are property names (e.g., STEPS.OPT_DESIGN.ARGS.DIRECTIVE), values are property values. Maps to set_property -name <key> -value <value>.",
    )
    environment_setup: Optional[dict[str, str]] = Field(
        default=None,
        description="Scripts to execute before processing. Keys are executors (e.g., bash, python), values are script paths relative to the config file. Script output lines in KEY=VALUE format are added to environment.",
    )
    hdlproject_config_version: Optional[str] = Field(
        default="3.0.0",
        description="Configuration schema version for compatibility checking.",
    )

    def to_json_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(exclude_unset=True, exclude_none=True)

    def to_json(self, **kwargs) -> str:
        """Convert to JSON string."""
        import json

        data = self.to_json_dict()
        return json.dumps(data, **kwargs)
