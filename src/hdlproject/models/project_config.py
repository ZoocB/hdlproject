"""Root project configuration model (`hdlproject_project_config.yaml`)."""

from typing import Any, Optional

from pydantic import Field

from hdlproject.models.base import FlexibleModel
from hdlproject.models.build import (
    BlockDesign,
    BuildConfiguration,
    Constraint,
    HooksConfig,
)
from hdlproject.models.device import ProjectInformation
from hdlproject.models.global_config import GlobalConfiguration
from hdlproject.models.tool import ToolExecutor


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
    set_property -name STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY -value rebuilt \
-objects [get_runs synth_1]
    ```
    """

    project_information: ProjectInformation = Field(
        description="Core project identification and settings."
    )
    hdldepends_config: Optional[str] = Field(
        default=None,
        description=(
            "Project-specific hdldepends config path. Overrides global setting."
        ),
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
        description=(
            "TCL hook points for injecting custom commands at workflow "
            "lifecycle stages."
        ),
    )
    environment_setup: Optional[dict[str, str]] = Field(
        default=None,
        description=(
            "Pre-processing scripts. Keys: executor, Values: script path. "
            "Output KEY=VALUE lines added to env."
        ),
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
            available.extend(f"{tool}/{v}" for v in self.tools[tool].keys())
        if tool in global_config.tools:
            available.extend(f"{tool}/{v}" for v in global_config.tools[tool].keys())

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
