"""Unified configuration loading.

This module provides a single entry point for loading all configuration:
global configuration, project configuration, and creating runtime contexts.
"""

from pathlib import Path
from typing import Optional

import yaml

from hdlproject.config.project_resolver import ProjectConfigResolver
from hdlproject.config.yaml_loader import YAMLConfigLoader
from hdlproject.constants import GLOBAL_CONFIG_FILENAME, PROJECT_CONFIG_FILENAME
from hdlproject.models import GlobalConfiguration, ProjectConfiguration
from hdlproject.models.resolved import ResolvedProjectConfig
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

        config_path = self.repository_root / GLOBAL_CONFIG_FILENAME

        if not config_path.exists():
            raise FileNotFoundError(
                f"Global configuration file not found: {config_path}\n"
                f"Please create {GLOBAL_CONFIG_FILENAME} at repository root with:\n"
                f'  project_dir: "projects"\n'
                f"  tools:\n"
                f"    vivado:\n"
                f'      "2020.1":\n'
                f"        setup:\n"
                f'          - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"\n'
                f'        executable: "vivado"'
            )

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f) or {}

            logger.info(f"Loaded global configuration from {config_path}")

            # Validate with Pydantic (no environment_setup for global config,
            # so no captured env to add to the ${VAR} expansion context)
            self._global_config = GlobalConfiguration.model_validate(
                data, context={"env": {}}
            )
            logger.debug(
                f"Global config: project_dir={self._global_config.project_dir}"
            )

            return self._global_config

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
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
        config, _captured_env = self._load_project_config_with_env(project_name)
        return config

    def _load_project_config_with_env(
        self, project_name: str
    ) -> tuple[ProjectConfiguration, dict[str, str]]:
        """Load a project's configuration and its captured setup environment.

        Same as ``load_project_config`` but also returns the KEY=VALUE pairs
        captured from the project's ``environment_setup`` scripts (empty dict
        if none configured), for callers that need to thread them onward
        (e.g. into ``ResolvedProjectConfig``) without touching ``os.environ``.

        Args:
            project_name: Name of the project directory

        Returns:
            Tuple of (ProjectConfiguration model, captured environment dict)

        Raises:
            FileNotFoundError: If project or config file doesn't exist
            ValueError: If configuration is invalid
        """
        global_config = self.load_global_config()
        projects_base_dir = self.repository_root / global_config.project_dir
        project_dir = projects_base_dir / project_name

        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        config_path = project_dir / PROJECT_CONFIG_FILENAME

        if not config_path.exists():
            raise FileNotFoundError(
                f"No configuration file found for project '{project_name}'\n"
                f"Expected: {config_path}"
            )

        try:
            # Load with inheritance processing
            resolved_dict = self.yaml_loader.load_with_inheritance(config_path)

            # Execute environment setup if specified, capturing its output
            # so ${VAR} expansion below can see it without touching os.environ
            captured_env: dict[str, str] = {}
            if "environment_setup" in resolved_dict:
                captured_env = self._run_environment_setup(
                    resolved_dict["environment_setup"], config_path.parent
                )

            # Validate with Pydantic, making the captured env available to
            # ${VAR} expansion for this project's own config fields
            config = ProjectConfiguration.model_validate(
                resolved_dict, context={"env": captured_env}
            )
            logger.info(f"Loaded project configuration: {project_name}")

            return config, captured_env

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
        project_config, captured_env = self._load_project_config_with_env(
            project_name
        )

        # Resolve paths
        projects_base_dir = self.repository_root / global_config.project_dir
        project_dir = projects_base_dir / project_name

        # Use ProjectConfigResolver to merge and resolve everything
        resolver = ProjectConfigResolver()
        resolved = resolver.resolve(
            global_config=global_config,
            project_config=project_config,
            project_name=project_name,
            project_dir=project_dir,
            repository_root=self.repository_root,
            environment=captured_env,
        )

        logger.debug(f"Resolved configuration for {project_name}")
        return resolved

    def _run_environment_setup(
        self,
        setup_config: dict[str, str],
        base_dir: Path,
    ) -> dict[str, str]:
        """Run environment setup scripts and capture their output.

        Does not mutate ``os.environ`` — callers thread the returned dict
        through explicitly (env-var expansion context, subprocess env) so
        that one project's setup cannot leak into another.

        Args:
            setup_config: Dict mapping executor to script path
            base_dir: Base directory for relative script paths

        Returns:
            Dict of KEY=VALUE pairs captured from script stdout
        """
        import subprocess

        logger.info("Executing environment setup scripts...")

        captured_env: dict[str, str] = {}

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
                        captured_env[key.strip()] = value.strip()
                        logger.debug(f"Captured environment: {key.strip()}")

            except subprocess.CalledProcessError as e:
                logger.error(f"Setup script failed: {e.stderr}")
                raise RuntimeError(
                    f"Environment setup failed: {script_path}"
                ) from e

        return captured_env
