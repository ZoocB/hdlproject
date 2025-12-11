# handlers/services/project_loader.py
"""Service for loading and validating project configurations.

This module provides a service layer for loading projects using the
ConfigLoader and returning ProjectRuntime objects.
"""

from typing import Optional

from hdlproject.models.models import GlobalConfiguration
from hdlproject.config.loader import ConfigLoader
from hdlproject.runtime.context import ProjectRuntime
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ProjectLoaderService:
    """Service for loading and validating project configurations.

    Uses ConfigLoader to load projects and creates ProjectRuntime objects
    ready for execution.
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
        check_vivado_executor: bool = True,
    ) -> list[ProjectRuntime]:
        """Load and validate all projects.

        Args:
            project_names: List of project names to load
            check_files: Whether to validate that files exist
            check_vivado_executor: Whether to validate that vivado_executor is configured

        Returns:
            List of ProjectRuntime objects

        Raises:
            RuntimeError: If any project fails to load or validate
        """
        runtimes = []

        for project_name in project_names:
            try:
                runtime = self.load_single_project(project_name)
                runtimes.append(runtime)
            except Exception as e:
                logger.error(f"Failed to load project '{project_name}': {e}")
                raise RuntimeError(f"Project loading failed: {project_name}") from e

        # Validate all projects
        errors = self.validate_projects(
            runtimes,
            check_files=check_files,
            check_vivado_executor=check_vivado_executor,
        )

        if errors:
            error_msg = "Project validation failed:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            # Log before raising so error is visible even if exception is caught silently
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return runtimes

    def load_single_project(self, project_name: str) -> ProjectRuntime:
        """Load configuration for a single project.

        Args:
            project_name: Name of project to load

        Returns:
            ProjectRuntime with loaded configuration
        """
        runtime = self.config_loader.create_project_runtime(
            project_name,
            self.global_config,
        )
        return runtime

    def validate_projects(
        self,
        runtimes: list[ProjectRuntime],
        check_files: bool = True,
        check_vivado_executor: bool = True,
    ) -> list[str]:
        """Validate all project runtimes.

        Args:
            runtimes: List of ProjectRuntime objects to validate
            check_files: Whether to check that files exist
            check_vivado_executor: Whether to check that vivado_executor is configured

        Returns:
            List of error messages (empty if all valid)
        """
        all_errors = []

        for runtime in runtimes:
            errors = runtime.validate(
                check_files=check_files,
                check_vivado_executor=check_vivado_executor,
            )
            if errors:
                all_errors.extend(
                    [f"{runtime.project_name}: {error}" for error in errors]
                )

        return all_errors
