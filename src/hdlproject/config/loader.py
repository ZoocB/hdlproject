"""Unified configuration loading.

This module provides a single entry point for loading all configuration:
global configuration, project configuration, and creating runtime contexts.
"""

import yaml
from pathlib import Path
from typing import Optional

from hdlproject.models.models import GlobalConfiguration, ProjectConfiguration
from hdlproject.models.resolved import ResolvedProjectConfig
from hdlproject.config.config_resolver import YAMLConfigLoader
from hdlproject.config.resolver import ConfigResolver
from hdlproject.runtime.context import RuntimeEnvironment
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """Unified configuration loader.

    Single entry point for all configuration loading. Handles:
    - Global configuration (hdlproject_global_config.yaml)
    - Project configuration with inheritance
    - Runtime context creation
    """

    GLOBAL_CONFIG_FILENAME = "hdlproject_global_config.yaml"
    PROJECT_CONFIG_FILENAME = "hdlproject_project_config.yaml"

    def __init__(self, repository_root: Path):
        """initialise the config loader.

        Args:
            repository_root: Path to the git repository root
        """
        self.repository_root = repository_root.resolve()
        self.yaml_loader = YAMLConfigLoader()
        self._global_config: Optional[GlobalConfiguration] = None

    def load_global_config(self) -> GlobalConfiguration:
        """Load the global configuration.

        Returns:
            GlobalConfiguration model

        Raises:
            FileNotFoundError: If global config file doesn't exist
            ValueError: If configuration is invalid
        """
        if self._global_config is not None:
            return self._global_config

        config_path = self.repository_root / self.GLOBAL_CONFIG_FILENAME

        if not config_path.exists():
            raise FileNotFoundError(
                f"Global configuration file not found: {config_path}\n"
                f"Please create {self.GLOBAL_CONFIG_FILENAME} at repository root with:\n"
                f'  project_dir: "projects"\n'
                f"  vivado_executors:\n"
                f'    "2020.1":\n'
                f"      commands:\n"
                f'        - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"'
            )

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f) or {}

            logger.info(f"Loaded global configuration from {config_path}")

            # Validate with Pydantic
            self._global_config = GlobalConfiguration(**data)
            logger.debug(
                f"Global config: project_dir={self._global_config.project_dir}"
            )

            return self._global_config

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to load global configuration: {e}")
            raise

    def load_project_config(self, project_name: str) -> ProjectConfiguration:
        """Load a project's configuration with inheritance.

        Args:
            project_name: Name of the project directory

        Returns:
            ProjectConfiguration model

        Raises:
            FileNotFoundError: If project or config file doesn't exist
            ValueError: If configuration is invalid
        """
        global_config = self.load_global_config()
        projects_base_dir = self.repository_root / global_config.project_dir
        project_dir = projects_base_dir / project_name

        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        config_path = project_dir / self.PROJECT_CONFIG_FILENAME

        if not config_path.exists():
            raise FileNotFoundError(
                f"No configuration file found for project '{project_name}'\n"
                f"Expected: {config_path}"
            )

        try:
            # Load with inheritance processing
            resolved_dict = self.yaml_loader.load_with_inheritance(config_path)

            # Execute environment setup if specified
            if "environment_setup" in resolved_dict:
                self._execute_environment_setup(
                    resolved_dict["environment_setup"], config_path.parent
                )

            # Validate with Pydantic
            config = ProjectConfiguration(**resolved_dict)
            logger.info(f"Loaded project configuration: {project_name}")

            return config

        except Exception as e:
            logger.error(f"Failed to load configuration for {project_name}: {e}")
            raise

    def create_runtime_environment(
        self,
        vivado_location: Optional[Path] = None,
    ) -> RuntimeEnvironment:
        """Create a runtime environment.

        Args:
            vivado_location: Optional Vivado installation location for validation

        Returns:
            RuntimeEnvironment with global config loaded
        """
        global_config = self.load_global_config()

        return RuntimeEnvironment(
            repository_root=self.repository_root,
            global_config=global_config,
            vivado_location=vivado_location,
        )

    def resolve_project_config(
        self,
        project_name: str,
        global_config: Optional[GlobalConfiguration] = None,
    ) -> ResolvedProjectConfig:
        """Load and resolve a project's configuration into a flat resolved config.

        Merges global + project configuration, resolves all paths to absolute,
        and pre-computes derived values.

        Args:
            project_name: Name of the project directory
            global_config: Global config (loaded if not provided)

        Returns:
            ResolvedProjectConfig ready for execution
        """
        if global_config is None:
            global_config = self.load_global_config()

        # Load project config
        project_config = self.load_project_config(project_name)

        # Resolve paths
        projects_base_dir = self.repository_root / global_config.project_dir
        project_dir = projects_base_dir / project_name

        # Use ConfigResolver to merge and resolve everything
        resolver = ConfigResolver()
        resolved = resolver.resolve(
            global_config=global_config,
            project_config=project_config,
            project_name=project_name,
            project_dir=project_dir,
            repository_root=self.repository_root,
        )

        logger.debug(f"Resolved configuration for {project_name}")
        return resolved

    def _execute_environment_setup(
        self,
        setup_config: dict[str, str],
        base_dir: Path,
    ) -> None:
        """Execute environment setup scripts.

        Args:
            setup_config: Dict mapping executor to script path
            base_dir: Base directory for relative script paths
        """
        import subprocess
        import os

        logger.info("Executing environment setup scripts...")

        for executor, script_path in setup_config.items():
            script_full_path = (base_dir / script_path).resolve()

            if not script_full_path.exists():
                logger.warning(f"Setup script not found: {script_full_path}")
                continue

            logger.info(f"Running: {executor} {script_full_path}")

            try:
                result = subprocess.run(
                    [executor, str(script_full_path)],
                    capture_output=True,
                    text=True,
                    cwd=base_dir,
                    check=True,
                )

                # Parse KEY=VALUE from output
                for line in result.stdout.splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
                        logger.debug(f"Set environment: {key.strip()}")

            except subprocess.CalledProcessError as e:
                logger.error(f"Setup script failed: {e.stderr}")
                raise RuntimeError(f"Environment setup failed: {script_path}")
