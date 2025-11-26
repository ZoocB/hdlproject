# handlers/services/project_loader.py
"""Service for loading and validating project configurations"""

from pathlib import Path
from typing import Any

from hdlproject.config.project_config import ProjectConfig
from hdlproject.handlers.base.context import ProjectContext
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ProjectLoader:
    """Handles all project loading and validation"""

    def __init__(self, environment: dict[str, Any]):
        """
        Initialise loader with environment configuration.

        Args:
            environment: dict with 'project_dir', 'repository_root', 'vivado_location'
        """
        self.projects_base_dir = Path(environment["project_dir"])
        self.repository_root = Path(environment["repository_root"])
        self.vivado_location = Path(environment["vivado_location"])

    def load_projects(
        self, project_names: list[str], operation_name: str, check_vivado: bool = True
    ) -> list[ProjectContext]:
        """
        Load and validate all projects.

        Args:
            project_names: list of project names to load
            operation_name: Name of operation (for paths)
            check_vivado: Whether to validate Vivado installation exists (default: True)

        Returns:
            list of ProjectContext objects

        Raises:
            RuntimeError: If any project fails to load or validate
        """
        contexts = []

        for project_name in project_names:
            try:
                context = self.load_single_project(
                    project_name, operation_name, check_vivado
                )
                contexts.append(context)
            except Exception as e:
                logger.error(f"Failed to load project '{project_name}': {e}")
                raise RuntimeError(f"Project loading failed: {project_name}") from e

        # Validate all projects (skip Vivado check if requested)
        errors = self.validate_projects(contexts, check_vivado)
        if errors:
            error_msg = "Project validation failed:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            raise RuntimeError(error_msg)

        return contexts

    def load_single_project(
        self,
        project_name: str,
        operation_name: str = "build",
        check_vivado: bool = True,
    ) -> ProjectContext:
        """
        Load configuration for a single project.

        Args:
            project_name: Name of project to load
            operation_name: Operation name for paths (default: build)
            check_vivado: Whether to validate Vivado installation exists (default: True)

        Returns:
            ProjectContext with loaded configuration
        """
        # Load project configuration
        config = ProjectConfig.load_from_yaml(
            project_name=project_name,
            projects_base_dir=self.projects_base_dir,
            vivado_location=self.vivado_location,
            repository_root=self.repository_root,
            check_if_vivado_version_exists=check_vivado,
        )

        # Get operation paths
        operation_paths = config.get_operation_paths(operation_name)

        return ProjectContext(config=config, operation_paths=operation_paths)

    def validate_projects(
        self, contexts: list[ProjectContext], check_vivado: bool = True
    ) -> list[str]:
        """
        Validate all project configurations.

        Args:
            contexts: list of ProjectContext objects to validate
            check_vivado: Whether to validate Vivado installation (default: True)

        Returns:
            list of error messages (empty if all valid)
        """
        all_errors = []

        for context in contexts:
            errors = context.config.validate(check_vivado=check_vivado)
            if errors:
                all_errors.extend(
                    [f"{context.config.name}: {error}" for error in errors]
                )

        return all_errors
