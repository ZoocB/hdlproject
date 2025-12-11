"""Runtime context objects for handler execution.

This module contains mutable runtime state that is separate from the immutable
Pydantic configuration models. Runtime objects are created per execution and
are safe for parallel processing.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hdlproject.models.models import (
        GlobalConfiguration,
        ProjectConfiguration,
        VivadoExecutor,
    )


# =============================================================================
# Path Management
# =============================================================================


@dataclass
class OperationPaths:
    """Standardised paths for any operation.

    Immutable after creation. Each operation (build, export, open) gets its own
    set of paths under the project's .hdlproject-vivado directory.
    """

    operation_dir: Path
    logs_dir: Path
    project_dir: Path  # Vivado .xpr location
    bd_dir: Path
    xci_dir: Path

    def get_log_file(self, operation: str) -> Path:
        """Get log file path for operation."""
        return self.logs_dir / f"{operation}.log"

    def get_project_file(self, vivado_project_name: str) -> Path:
        """Get path to Vivado project file (.xpr).

        Args:
            vivado_project_name: The Vivado project name (from YAML config),
                                 NOT the directory name.
        """
        return self.project_dir / f"{vivado_project_name}.xpr"

    def create_directories(self) -> None:
        """Create all operation directories."""
        for path in [self.logs_dir, self.project_dir, self.bd_dir, self.xci_dir]:
            path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Runtime Environment
# =============================================================================


@dataclass
class RuntimeEnvironment:
    """Global runtime environment, created once per CLI invocation.

    This is shared (read-only) across all projects being processed.
    Contains the global configuration and repository-level paths.
    """

    repository_root: Path
    global_config: "GlobalConfiguration"
    vivado_location: Optional[Path] = None  # For validation only, not execution

    @property
    def projects_base_dir(self) -> Path:
        """Get the base directory containing all projects."""
        return self.repository_root / self.global_config.project_dir


# =============================================================================
# Project Runtime
# =============================================================================


@dataclass
class ProjectRuntime:
    """Runtime context for a single project.

    Created per project being processed. Thread-safe: each parallel worker
    gets its own instance. Contains the immutable configuration plus
    mutable runtime state like resolved paths.
    """

    # Immutable configuration reference
    config: "ProjectConfiguration"

    # Resolved paths
    project_dir: (
        Path  # The project's directory (contains hdlproject_project_config.yaml)
    )
    repository_root: Path

    # Mutable state set during execution
    resolved_config_path: Optional[Path] = None
    compile_order_path: Optional[Path] = None
    top_level_file_path: Optional[Path] = None

    # Reference to global config for resolution methods
    _global_config: Optional["GlobalConfiguration"] = field(default=None, repr=False)

    def get_operation_paths(self, operation: str) -> OperationPaths:
        """Get standardised paths for an operation.

        Args:
            operation: Operation name (build, export, open, etc.)

        Returns:
            OperationPaths with all directories for this operation
        """
        hdlproject_dir = self.project_dir / ".hdlproject-vivado"
        operation_dir = hdlproject_dir / operation

        return OperationPaths(
            operation_dir=operation_dir,
            logs_dir=operation_dir / "logs",
            project_dir=operation_dir / "project",
            bd_dir=operation_dir / "bd",
            xci_dir=operation_dir / "xci",
        )

    def get_vivado_executor(self) -> "VivadoExecutor":
        """Get the Vivado executor for this project.

        Returns:
            VivadoExecutor with commands to set up environment

        Raises:
            RuntimeError: If global config not set
        """
        if self._global_config is None:
            raise RuntimeError("Global config not set on ProjectRuntime")
        return self.config.get_vivado_executor(self._global_config)

    def get_hdldepends_path(self) -> Optional[Path]:
        """Get the resolved hdldepends config path.

        Resolution order:
        1. Project-level (relative to project_dir)
        2. Global-level (relative to repository_root)

        Returns:
            Absolute path to hdldepends config, or None if not configured

        Raises:
            FileNotFoundError: If configured path doesn't exist
        """
        if self._global_config is None:
            raise RuntimeError("Global config not set on ProjectRuntime")

        # Check project-level first
        if self.config.hdldepends_config:
            path = self.project_dir / self.config.hdldepends_config
            if not path.exists():
                raise FileNotFoundError(
                    f"Project hdldepends config not found: {path}\n"
                    f"  Specified in: {self.project_dir / 'hdlproject_project_config.yaml'}"
                )
            return path.resolve()

        # Fall back to global
        if self._global_config.hdldepends_config:
            path = self.repository_root / self._global_config.hdldepends_config
            if not path.exists():
                raise FileNotFoundError(
                    f"Global hdldepends config not found: {path}\n"
                    f"  Specified in: {self.repository_root / 'hdlproject_global_config.yaml'}"
                )
            return path.resolve()

        return None

    def get_tcl_arguments(
        self,
        mode: str,
        operation_paths: OperationPaths,
        cores: int = 1,
    ) -> list[str]:
        """Get TCL script arguments for Vivado execution.

        Args:
            mode: TCL script mode (build, open, export)
            operation_paths: Paths for this operation
            cores: Number of CPU cores to use

        Returns:
            List of command-line arguments for TCL script

        Raises:
            RuntimeError: If resolved config path not set
        """
        if not self.resolved_config_path:
            raise RuntimeError("Configuration not resolved for operation")

        return [
            "--mode",
            mode,
            "--vivado-project-dir",
            str(operation_paths.project_dir),
            "--project-root",
            str(self.project_dir),
            "--cores",
            str(cores),
            "--config",
            str(self.resolved_config_path),
        ]

    def export_resolved_config(self, output_dir: Path) -> Path:
        """Export the resolved configuration as JSON for TCL scripts.

        Args:
            output_dir: Directory to save the JSON file

        Returns:
            Path to the saved JSON file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "hdlproject_config_resolved.json"

        with open(json_path, "w") as f:
            f.write(self.config.to_json(indent=2))

        self.resolved_config_path = json_path
        return json_path

    def validate(
        self,
        check_files: bool = True,
        check_vivado_executor: bool = True,
    ) -> list[str]:
        """Validate the project runtime configuration.

        Args:
            check_files: Whether to check that files exist
            check_vivado_executor: Whether to check that vivado_executor is configured

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check project directory
        if not self.project_dir.exists():
            errors.append(f"Project directory not found: {self.project_dir}")

        # Check vivado_executor is configured for this version
        if check_vivado_executor:
            try:
                self.get_vivado_executor()
            except ValueError as e:
                errors.append(str(e))

        if check_files:
            # Check top-level file
            if not self.top_level_file_path:
                errors.append(
                    f"Top-level file '{self.config.project_information.top_level_file_name}' "
                    f"not found in repository"
                )
            elif not self.top_level_file_path.exists():
                errors.append(
                    f"Top-level file not found at: {self.top_level_file_path}"
                )

            # Check hdldepends config if specified
            try:
                hdldepends_path = self.get_hdldepends_path()
                if hdldepends_path and not hdldepends_path.exists():
                    errors.append(f"HDLDepends config not found: {hdldepends_path}")
            except FileNotFoundError as e:
                errors.append(str(e))

        return errors

    def find_top_level_file(self) -> Optional[Path]:
        """Find the top-level HDL file in the repository.

        Searches for files matching the top_level_file_name with common
        HDL extensions.

        Returns:
            Path to the top-level file, or None if not found
        """
        from hdlproject.utils.logging_manager import get_logger

        logger = get_logger(__name__)

        top_name = self.config.project_information.top_level_file_name
        extensions = [".vhd", ".vhdl", ".v", ".sv"]
        found_files = []

        for ext in extensions:
            pattern = f"{top_name}{ext}"
            found_files.extend(self.repository_root.rglob(pattern))

        if not found_files:
            logger.warning(
                f"Top-level file '{top_name}' not found in {self.repository_root}"
            )
            return None

        if len(found_files) > 1:
            logger.warning(f"Multiple files found for '{top_name}': {found_files}")

        return found_files[0]

    @property
    def project_name(self) -> str:
        """Get the project identifier (directory name).

        This is used for:
        - CLI/TUI project selection
        - Status display tracking
        - Log file naming
        - Internal identification
        """
        return self.project_dir.name

    @property
    def vivado_project_name(self) -> str:
        """Get the Vivado project name from configuration.

        This is the name used for the .xpr file and within Vivado.
        May differ from the directory name (project_name).
        """
        return self.config.project_information.project_name

    @property
    def vivado_version(self) -> str:
        """Get the Vivado version string."""
        return self.config.project_information.vivado_version.full_version

    @property
    def device_part(self) -> str:
        """Get the FPGA part name."""
        return self.config.project_information.device_info.part_name


# =============================================================================
# Execution Contexts
# =============================================================================


@dataclass
class ExecutionServices:
    """Services available to handlers during execution.

    These are stateless services that can be safely shared across threads.
    """

    vivado_executor: Any  # VivadoExecutorService
    status_manager: Any  # StatusManager
    compile_order_service: Any  # CompileOrderService (can be None)


@dataclass
class ExecutionContext:
    """Context for handler execution across all projects.

    Passed to handler.configure() and used for orchestration.
    """

    environment: RuntimeEnvironment
    project_runtimes: list[ProjectRuntime]
    handler_options: Any  # BuildHandlerOptions, ExportHandlerOptions, etc.
    operation_config: Any  # OperationConfig from handler
    services: ExecutionServices


@dataclass
class SingleProjectExecution:
    """Context for processing a single project.

    Passed to handler.prepare() and handler.execute_single().
    Each parallel worker gets its own instance.
    """

    runtime: ProjectRuntime
    operation_paths: OperationPaths
    handler_options: Any
    operation_config: Any
    services: ExecutionServices

    @property
    def project_name(self) -> str:
        """Convenience access to project name."""
        return self.runtime.project_name
