"""Configuration resolver.

Merges GlobalConfiguration + ProjectConfiguration into a single
ResolvedProjectConfig with all paths resolved to absolute and all
derived values pre-computed.
"""

from pathlib import Path
from typing import Optional

from hdlproject.models.models import (
    GlobalConfiguration,
    ProjectConfiguration,
    VivadoExecutor,
)
from hdlproject.models.resolved import (
    ResolvedProjectConfig,
    ResolvedPaths,
    ResolvedOperationPaths,
    KNOWN_OPERATIONS,
)
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ConfigResolver:
    """Resolves global + project configuration into a flat ResolvedProjectConfig.

    Merge rules:
    - vivado_executor: project version wins over global version
    - hdldepends_config: project overrides global
    - compile_order_format, default_cores, max_parallel_builds: from global only
    - Everything else: from project config only

    Path resolution:
    - Paths from global config are relative to repository_root
    - Paths from project config are relative to project_dir
    - All stored as absolute paths in the resolved config
    """

    def resolve(
        self,
        global_config: GlobalConfiguration,
        project_config: ProjectConfiguration,
        project_name: str,
        project_dir: Path,
        repository_root: Path,
    ) -> ResolvedProjectConfig:
        """Create a fully resolved configuration for a project.

        Args:
            global_config: Global repository configuration
            project_config: Project-specific configuration
            project_name: Directory name of the project
            project_dir: Absolute path to the project directory
            repository_root: Absolute path to the repository root

        Returns:
            ResolvedProjectConfig with everything pre-computed
        """
        # Resolve the vivado executor (project -> global fallback)
        vivado_executor = self._resolve_vivado_executor(
            global_config, project_config
        )

        # Resolve hdldepends config path
        hdldepends_config_path = self._resolve_hdldepends_path(
            global_config, project_config, project_dir, repository_root
        )

        # Find top-level file
        top_level_file_path = self._find_top_level_file(
            project_config.project_information.top_level_file_name,
            repository_root,
        )

        # Build resolved paths
        hdlproject_dir = project_dir / ".hdlproject-vivado"
        paths = ResolvedPaths(
            repository_root=repository_root,
            project_dir=project_dir,
            hdlproject_dir=hdlproject_dir,
            top_level_file_path=top_level_file_path,
            hdldepends_config_path=hdldepends_config_path,
        )

        # Pre-compute operation paths for all known operations
        operation_paths = {}
        for operation in KNOWN_OPERATIONS:
            operation_paths[operation] = self._build_operation_paths(
                hdlproject_dir, operation
            )

        return ResolvedProjectConfig(
            # Identity
            project_name=project_name,
            vivado_project_name=project_config.project_information.project_name,
            # Paths
            paths=paths,
            operation_paths=operation_paths,
            # Project config (passed through)
            project_information=project_config.project_information,
            constraints=project_config.constraints,
            block_designs=project_config.block_designs,
            synth_options=project_config.synth_options,
            impl_options=project_config.impl_options,
            build_configuration=project_config.build_configuration,
            environment_setup=project_config.environment_setup,
            # Merged settings
            vivado_executor=vivado_executor,
            compile_order_format=global_config.compile_order_format,
            default_cores=global_config.default_cores,
            max_parallel_builds=global_config.max_parallel_builds,
        )

    def _resolve_vivado_executor(
        self,
        global_config: GlobalConfiguration,
        project_config: ProjectConfiguration,
    ) -> VivadoExecutor:
        """Resolve the vivado executor for this project's version.

        Resolution order: project -> global.

        Raises:
            ValueError: If no executor configured for the required version
        """
        return project_config.get_vivado_executor(global_config)

    def _resolve_hdldepends_path(
        self,
        global_config: GlobalConfiguration,
        project_config: ProjectConfiguration,
        project_dir: Path,
        repository_root: Path,
    ) -> Optional[Path]:
        """Resolve hdldepends config to an absolute path.

        Resolution order:
        1. Project-level (relative to project_dir)
        2. Global-level (relative to repository_root)

        Returns:
            Absolute path to hdldepends config, or None if not configured

        Raises:
            FileNotFoundError: If configured path doesn't exist
        """
        # Check project-level first
        if project_config.hdldepends_config:
            path = project_dir / project_config.hdldepends_config
            if not path.exists():
                raise FileNotFoundError(
                    f"Project hdldepends config not found: {path}\n"
                    f"  Specified in: {project_dir / 'hdlproject_project_config.yaml'}"
                )
            return path.resolve()

        # Fall back to global
        if global_config.hdldepends_config:
            path = repository_root / global_config.hdldepends_config
            if not path.exists():
                raise FileNotFoundError(
                    f"Global hdldepends config not found: {path}\n"
                    f"  Specified in: {repository_root / 'hdlproject_global_config.yaml'}"
                )
            return path.resolve()

        return None

    def _find_top_level_file(
        self,
        top_level_file_name: str,
        repository_root: Path,
    ) -> Optional[Path]:
        """Find the top-level HDL file in the repository.

        Searches for files matching the name with common HDL extensions.

        Returns:
            Absolute path to the top-level file, or None if not found
        """
        extensions = [".vhd", ".vhdl", ".v", ".sv"]
        found_files = []

        for ext in extensions:
            pattern = f"{top_level_file_name}{ext}"
            found_files.extend(repository_root.rglob(pattern))

        if not found_files:
            logger.warning(
                f"Top-level file '{top_level_file_name}' not found "
                f"in {repository_root}"
            )
            return None

        if len(found_files) > 1:
            logger.warning(
                f"Multiple files found for '{top_level_file_name}': {found_files}"
            )

        return found_files[0].resolve()

    def _build_operation_paths(
        self,
        hdlproject_dir: Path,
        operation: str,
    ) -> ResolvedOperationPaths:
        """Build operation paths for a given operation.

        Args:
            hdlproject_dir: The .hdlproject-vivado directory
            operation: Operation name (build, export, open)

        Returns:
            ResolvedOperationPaths with all directories
        """
        operation_dir = hdlproject_dir / operation

        return ResolvedOperationPaths(
            operation=operation,
            operation_dir=operation_dir,
            logs_dir=operation_dir / "logs",
            project_dir=operation_dir / "project",
            bd_dir=operation_dir / "bd",
            xci_dir=operation_dir / "xci",
        )
