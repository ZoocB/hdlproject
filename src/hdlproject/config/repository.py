"""Repository-specific configuration management"""

import yaml
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


@dataclass
class RepositoryConfig:
    """Global repository configuration from hdlproject_global_config.yaml"""
    project_dir: str  # Required - base directory for all projects
    hdldepends_config: Optional[str] = None  # Optional - default path to hdldepends config file
    compile_order_script_format: str = "json"
    default_cores_per_project: int = 2
    max_parallel_builds: Optional[int] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class RepositoryConfigManager:
    """Manages repository-specific configuration from hdlproject_global_config.yaml."""
    
    CONFIG_FILENAME = "hdlproject_global_config.yaml"
    
    def __init__(self, git_root: Path):
        self.git_root = git_root
        self.config_path = git_root / self.CONFIG_FILENAME
        self._config: Optional[RepositoryConfig] = None
    
    def load(self) -> RepositoryConfig:
        """
        Load configuration from YAML file.
        
        Returns:
            RepositoryConfig with validated values
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If required fields are missing
        """
        if self._config is not None:
            return self._config
        
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Global configuration file not found: {self.config_path}\n"
                f"Please create {self.CONFIG_FILENAME} at repository root with:\n"
                f"  project_dir: \"projects\""
            )
        
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded global configuration from {self.config_path}")
            
            # Validate required fields
            if 'project_dir' not in data:
                raise ValueError(
                    f"Missing required field 'project_dir' in {self.config_path}"
                )
            
            self._config = RepositoryConfig(
                project_dir=data['project_dir'],
                hdldepends_config=data.get('hdldepends_config'),
                compile_order_script_format=data.get('compile_order_script_format', 'json'),
                default_cores_per_project=data.get('default_cores_per_project', 2),
                max_parallel_builds=data.get('max_parallel_builds')
            )
            
            logger.debug(f"Global configuration: {self._config.to_dict()}")
            return self._config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {self.config_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error loading global configuration: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        config = self.load()
        return getattr(config, key, default)