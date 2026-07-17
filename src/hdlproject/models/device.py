"""Device and project-identity configuration models."""

from typing import Optional

from pydantic import Field

from hdlproject.models.base import FlexibleModel


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
        description=(
            "Xilinx board part identifier (e.g., "
            "digilentinc.com:arty-a7-35:part0:1.1)."
        ),
    )


class ProjectInformation(FlexibleModel):
    """Core project identification and settings.

    Example:
    ```yaml
    project_information:
      project_name: my_project
      top_level_file_name: top_level
      default_library: work
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
    default_library: str = Field(
        default="work",
        description=(
            "Default HDL library for compilation (Vivado's 'default_lib' "
            "project property). Defaults to 'work' if unset."
        ),
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
        """Get the year/major component of the tool version.

        E.g., '2020' from '2020.1'.
        """
        return self.tool_version.split(".")[0]

    @property
    def tool_version_minor(self) -> str:
        """Get the minor component of the tool version (e.g., '1' from '2020.1')."""
        parts = self.tool_version.split(".")
        return parts[1] if len(parts) > 1 else "0"
