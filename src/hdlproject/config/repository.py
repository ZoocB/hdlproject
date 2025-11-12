"""Repository-specific configuration management"""

import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


@dataclass
class RepositoryConfig:
    """Repository-specific configuration loaded from hdlproject-config.json"""
    project_dir: Optional[str] = None
    compile_order_script_format: str = "json"
    default_cores_per_project: int = 2
    max_parallel_builds: Optional[int] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class RepositoryConfigManager:
    """
    Manages repository-specific configuration from hdlproject-config.json.
    
    Configuration file should be placed at repository root.
    If not found, returns default values.
    """
    
    CONFIG_FILENAME = "hdlproject-config.json"
    
    def __init__(self, git_root: Path):
        self.git_root = git_root
        self.config_path = git_root / self.CONFIG_FILENAME
        self._config: Optional[RepositoryConfig] = None
    
    def load(self) -> RepositoryConfig:
        """
        Load configuration from file, or return defaults.
        
        Returns:
            RepositoryConfig with loaded or default values
        """
        if self._config is not None:
            return self._config
        
        if not self.config_path.exists():
            logger.debug(f"No repository config found at {self.config_path}, using defaults")
            self._config = RepositoryConfig()
            return self._config
        
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            logger.info(f"Loaded repository config from {self.config_path}")
            
            self._config = RepositoryConfig(
                project_dir=data.get('project_dir'),
                compile_order_script_format=data.get('compile_order_script_format', 'json'),
                default_cores_per_project=data.get('default_cores_per_project', 2),
                max_parallel_builds=data.get('max_parallel_builds')
            )
            
            logger.debug(f"Repository config: {self._config.to_dict()}")
            return self._config
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.config_path}: {e}")
            logger.warning("Using default configuration")
            self._config = RepositoryConfig()
            return self._config
        except Exception as e:
            logger.error(f"Error loading repository config: {e}")
            logger.warning("Using default configuration")
            self._config = RepositoryConfig()
            return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        config = self.load()
        return getattr(config, key, default)