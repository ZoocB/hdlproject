# handlers/services/project_loader.py
"""Service for loading and validating project configurations.

This module provides a service layer for loading projects using the
ConfigLoader and returning ResolvedProjectConfig objects.
"""

from hdlproject.config.loader import ConfigLoader
from hdlproject.models import GlobalConfiguration
from hdlproject.models.resolved import ResolvedProjectConfig
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ProjectLoaderService:
    """Service for loading and validating project configurations.

    Uses ConfigLoader to resolve projects and creates ResolvedProjectConfig
    objects ready for execution.
    """

    def __init__(
        self,
        config_loader: ConfigLoader,
        global_config: GlobalConfiguration,
    ):
        """initialise the project loader service.

        Args:
            config_loader: ConfigLoader instance for loading configs
            global_config: Global configuration
        """
        self.config_loader = config_loader
        self.global_config = global_config

    def load_projects(
        self,
        project_names: list[str],
        check_files: bool = True,
        check_executor: bool = True,
    ) -> list[ResolvedProjectConfig]:
        """Load and validate all projects.

        Args:
            project_names: List of project names to load
            check_files: Whether to validate that files exist
            check_executor: Whether to validate that vivado_executor is configured

        Returns:
            List of ResolvedProjectConfig objects

        Raises:
            RuntimeError: If any project fails to load or validate
        """
        configs = []

        for project_name in project_names:
            try:
                resolved = self.load_single_project(project_name)
                configs.append(resolved)
            except Exception as e:
                logger.error(f"Failed to load project '{project_name}': {e}")
                raise RuntimeError(f"Project loading failed: {project_name}") from e

        # Validate all projects
        errors = self.validate_projects(
            configs,
            check_files=check_files,
            check_executor=check_executor,
        )

        if errors:
            error_msg = "Project validation failed:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return configs

    def load_single_project(self, project_name: str) -> ResolvedProjectConfig:
        """Load and resolve configuration for a single project.

        Args:
            project_name: Name of project to load

        Returns:
            ResolvedProjectConfig with fully resolved configuration
        """
        return self.config_loader.resolve_project_config(
            project_name,
            self.global_config,
        )

    def validate_projects(
        self,
        configs: list[ResolvedProjectConfig],
        check_files: bool = True,
        check_executor: bool = True,
    ) -> list[str]:
        """Validate all resolved project configurations.

        Args:
            configs: List of ResolvedProjectConfig objects to validate
            check_files: Whether to check that files exist
            check_executor: Whether to check that vivado_executor is configured

        Returns:
            List of error messages (empty if all valid)
        """
        all_errors = []

        for config in configs:
            errors = config.validate_for_execution(
                check_files=check_files,
                check_executor=check_executor,
            )
            if errors:
                all_errors.extend(
                    [f"{config.project_name}: {error}" for error in errors]
                )

        return all_errors
