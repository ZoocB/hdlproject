"""Global (repository-wide) configuration model."""

from typing import Optional

from pydantic import Field

from hdlproject.models.base import FlexibleModel
from hdlproject.models.tool import ToolExecutor


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
