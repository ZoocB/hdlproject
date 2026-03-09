"""Resolved project configuration model.

This module contains the fully-resolved, flat configuration for a single project.
All paths are absolute, all global/project merging is complete, and all derived
values are pre-computed. This is the single source of truth passed around during
execution.
"""

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from hdlproject.models.models import (
    ProjectInformation,
    Constraint,
    BlockDesign,
    BuildConfiguration,
    HooksConfig,
    ToolExecutor,
)


# Known operations for pre-computing paths
KNOWN_OPERATIONS = ("build", "export", "open")

# Base directory prefix — tool name is appended (e.g., ".hdlproject-vivado")
HDLPROJECT_DIR_PREFIX = ".hdlproject"


def get_hdlproject_dir_name(tool: str) -> str:
    """Get the tool-specific output directory name.

    Args:
        tool: Tool name (e.g., 'vivado')

    Returns:
        Directory name like '.hdlproject-vivado'
    """
    return f"{HDLPROJECT_DIR_PREFIX}-{tool}"


class ResolvedPaths(BaseModel):
    """All pre-computed absolute paths for a project."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    repository_root: Path
    project_dir: Path
    hdlproject_dir: Path  # project_dir / .hdlproject-{tool}
    top_level_file_path: Optional[Path] = None
    hdldepends_config_path: Optional[Path] = None
    resolved_config_path: Optional[Path] = None  # set after export_to_disk


class ResolvedOperationPaths(BaseModel):
    """Pre-computed absolute paths for a single operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    operation: str
    operation_dir: Path
    logs_dir: Path
    project_dir: Path  # tool project location (e.g. .xpr for Vivado)
    bd_dir: Path
    xci_dir: Path

    def get_log_file(self, operation: str) -> Path:
        """Get log file path for operation."""
        return self.logs_dir / f"{operation}.log"

    def get_project_file(self, project_name: str) -> Path:
        """Get path to tool project file (e.g. .xpr for Vivado)."""
        return self.project_dir / f"{project_name}.xpr"

    def create_directories(self) -> None:
        """Create all operation directories."""
        for path in [self.logs_dir, self.project_dir, self.bd_dir, self.xci_dir]:
            path.mkdir(parents=True, exist_ok=True)


class ResolvedProjectConfig(BaseModel):
    """Fully resolved, flat configuration for a single project.

    Created by ConfigResolver from GlobalConfiguration + ProjectConfiguration.
    All paths are absolute, all merging is done, all derived values pre-computed.
    This replaces ProjectRuntime as the single object passed through the system.

    The entire model is serialized to JSON on disk so that external tools
    (e.g. TCL scripts) can read any value they need.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # === Identity ===
    project_name: str = Field(
        description="Directory name, used for CLI selection and logging."
    )
    vivado_project_name: str = Field(
        description="Tool project name from config, used for project file naming."
    )
    tool: str = Field(description="EDA tool name (e.g., 'vivado').")

    # === Pre-resolved paths ===
    paths: ResolvedPaths

    # === Pre-computed operation paths (keyed by operation name) ===
    operation_paths: dict[str, ResolvedOperationPaths] = Field(default_factory=dict)

    # === Project configuration (from YAML, already merged) ===
    project_information: ProjectInformation
    constraints: list[Constraint] = Field(default_factory=list)
    block_designs: list[BlockDesign] = Field(default_factory=list)
    synth_options: dict[str, str] = Field(default_factory=dict)
    impl_options: dict[str, str] = Field(default_factory=dict)
    build_configuration: BuildConfiguration = Field(default_factory=BuildConfiguration)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    environment_setup: Optional[dict[str, str]] = None

    # === Merged settings (global + project override) ===
    executor: ToolExecutor = Field(
        description="Resolved tool executor configuration (project overrides global)."
    )
    compile_order_format: str = "json"
    default_cores: int = 2
    max_parallel_builds: Optional[int] = None

    # === Convenience properties ===

    @property
    def tool_version(self) -> str:
        """Get the tool version string (e.g., '2020.1')."""
        return self.project_information.tool_version

    @property
    def device_part(self) -> str:
        """Get the FPGA part name."""
        return self.project_information.device_info.part_name

    @property
    def repository_root(self) -> Path:
        """Shortcut to paths.repository_root."""
        return self.paths.repository_root

    @property
    def project_dir(self) -> Path:
        """Shortcut to paths.project_dir."""
        return self.paths.project_dir

    # === Operation path access ===

    def get_operation_paths(self, operation: str) -> ResolvedOperationPaths:
        """Get pre-computed paths for an operation.

        Args:
            operation: Operation name (build, export, open)

        Returns:
            ResolvedOperationPaths for the operation

        Raises:
            KeyError: If operation paths not pre-computed
        """
        if operation not in self.operation_paths:
            raise KeyError(
                f"Operation '{operation}' not found in resolved config. "
                f"Available: {list(self.operation_paths.keys())}"
            )
        return self.operation_paths[operation]

    # === TCL integration ===

    def get_tcl_arguments(
        self,
        mode: str,
        operation: str,
        cores: int = 1,
    ) -> list[str]:
        """Get TCL script arguments for tool execution.

        Args:
            mode: TCL script mode (build, open, export)
            operation: Operation name to look up paths
            cores: Number of CPU cores to use

        Returns:
            List of command-line arguments for TCL script

        Raises:
            RuntimeError: If resolved config path not set
        """
        if not self.paths.resolved_config_path:
            raise RuntimeError("Configuration not exported to disk yet")

        op_paths = self.get_operation_paths(operation)

        return [
            "--mode",
            mode,
            "--vivado-project-dir",
            str(op_paths.project_dir),
            "--project-root",
            str(self.paths.project_dir),
            "--cores",
            str(cores),
            "--config",
            str(self.paths.resolved_config_path),
        ]

    def export_to_disk(self, output_dir: Path) -> Path:
        """Export the full resolved configuration as JSON.

        Serializes the entire ResolvedProjectConfig to disk so that
        external tools (TCL scripts, CI systems, etc.) have access to
        all resolved values including paths, executor config, and
        operation directories.

        Args:
            output_dir: Directory to save the JSON file

        Returns:
            Path to the saved JSON file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "hdlproject_config_resolved.json"

        # Serialize the full resolved config
        config_dict = self.model_dump(
            mode="json",
            exclude_none=True,
        )

        with open(json_path, "w") as f:
            json.dump(config_dict, f, indent=2, default=str)

        self.paths.resolved_config_path = json_path
        return json_path

    # === Validation ===

    def validate_for_execution(
        self,
        check_files: bool = True,
        check_executor: bool = True,
    ) -> list[str]:
        """Validate the resolved configuration is ready for execution.

        Args:
            check_files: Whether to check that files exist
            check_executor: Whether to check tool executor

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.paths.project_dir.exists():
            errors.append(f"Project directory not found: {self.paths.project_dir}")

        if check_files:
            if not self.paths.top_level_file_path:
                errors.append(
                    f"Top-level file '{self.project_information.top_level_file_name}' "
                    f"not found in repository"
                )
            elif not self.paths.top_level_file_path.exists():
                errors.append(
                    f"Top-level file not found at: {self.paths.top_level_file_path}"
                )

            if self.paths.hdldepends_config_path:
                if not self.paths.hdldepends_config_path.exists():
                    errors.append(
                        f"HDLDepends config not found: "
                        f"{self.paths.hdldepends_config_path}"
                    )

        return errors
