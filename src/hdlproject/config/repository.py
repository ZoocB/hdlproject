"""Repository-specific configuration management.

This module provides a manager for loading the global repository configuration.
The actual configuration model is defined in models.py.
"""

import yaml
from pathlib import Path
from typing import Any, Optional

from hdlproject.models.models import GlobalConfiguration
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class RepositoryConfigManager:
    """Manages repository-specific configuration from hdlproject_global_config.yaml.

    This is a thin wrapper that loads and caches the GlobalConfiguration model.
    For new code, prefer using ConfigLoader directly.
    """

    CONFIG_FILENAME = "hdlproject_global_config.yaml"

    def __init__(self, repository_root: Path):
        """initialise the repository config manager.

        Args:
            repository_root: Path to the git repository root
        """
        self.repository_root = repository_root
        self.config_path = repository_root / self.CONFIG_FILENAME
        self._config: Optional[GlobalConfiguration] = None

    def load(self) -> GlobalConfiguration:
        """Load configuration from YAML file.

        Returns:
            GlobalConfiguration model

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Global configuration file not found: {self.config_path}\n"
                f"Please create {self.CONFIG_FILENAME} at repository root with:\n"
                f'  project_dir: "projects"\n'
                f"  tools:\n"
                f"    vivado:\n"
                f'      "2020.1":\n'
                f"        setup:\n"
                f'          - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"\n'
                f'        executable: "vivado"'
            )

        try:
            with open(self.config_path, "r") as f:
                data = yaml.safe_load(f) or {}

            logger.info(f"Loaded global configuration from {self.config_path}")

            # Validate with Pydantic
            self._config = GlobalConfiguration(**data)

            logger.debug(f"Global config: project_dir={self._config.project_dir}")
            return self._config

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {self.config_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading global configuration: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Args:
            key: Configuration key name
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        config = self.load()
        return getattr(config, key, default)
