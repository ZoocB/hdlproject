# config/config_resolver.py
"""Configuration resolver with YAML support and inheritance"""

import yaml
import subprocess
from pathlib import Path
from typing import Any, Set, Optional
from copy import deepcopy
import os

from hdlproject.models.models import ProjectConfiguration
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class YAMLConfigLoader:
    """YAML configuration loader with inheritance support"""
    
    def load_with_inheritance(self, config_path: Path) -> dict[str, Any]:
        """Load configuration with inheritance processing"""
        return self._load_recursive(config_path, set())
    
    def _load_recursive(self, config_path: Path, visited: Set[str]) -> dict[str, Any]:
        """Recursively load configuration with inheritance"""
        # Check for circular dependencies
        abs_path = str(config_path.absolute())
        if abs_path in visited:
            raise RuntimeError(f"Circular dependency detected: {abs_path}")
        visited.add(abs_path)
        
        # Load file
        if config_path.suffix not in ['.yaml', '.yml']:
            raise ValueError(f"Only YAML configuration files are supported. Found: {config_path}")
            
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load YAML file {config_path}: {e}")
            raise RuntimeError(f"Failed to load YAML file: {e}")
        
        # Process inheritance
        if 'inherits' in data:
            inherits = data.pop('inherits')
            if isinstance(inherits, str):
                inherits = [inherits]
            
            # Start with empty base
            result = {}
            
            # Load each parent
            for parent_file in inherits:
                parent_path = (config_path.parent / parent_file).resolve()
                if not parent_path.exists():
                    raise FileNotFoundError(f"Parent configuration not found: {parent_path}")
                parent_data = self._load_recursive(parent_path, visited.copy())
                result = self._merge_configs(result, parent_data)
            
            # Merge current file on top
            return self._merge_configs(result, data)
        
        return data
    
    def _merge_configs(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge configurations"""
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = deepcopy(value)
        
        return result


class ConfigResolver:
    """Configuration resolver - simplified without complex error handling"""
    
    def __init__(self, base_dir: Path):
        """Initialise resolver"""
        self.base_dir = base_dir
        self.yaml_loader = YAMLConfigLoader()
    
    def resolve_config(self, config_path: Path, output_dir: Optional[Path] = None) -> ProjectConfiguration:
        """
        Resolve YAML configuration with inheritance and return Pydantic model
        
        Args:
            config_path: Path to YAML configuration file
            output_dir: Optional directory to save resolved configuration
            
        Returns:
            ProjectConfiguration: Validated Pydantic model
        """
        logger.info(f"Resolving configuration: {config_path}")
        
        # Ensure we have a YAML file
        if config_path.suffix not in ['.yaml', '.yml']:
            raise ValueError(
                f"Only YAML configuration files are supported. "
                f"Got: {config_path.name}"
            )
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load configuration with inheritance
        resolved_dict = self.yaml_loader.load_with_inheritance(config_path)
        
        # Execute environment setup if specified
        if 'environment_setup' in resolved_dict:
            self._execute_environment_setup(
                resolved_dict['environment_setup'], 
                config_path.parent
            )
        
        # Create and validate Pydantic model
        try:
            config = ProjectConfiguration(**resolved_dict)
            logger.info("Configuration validated successfully")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ValueError(f"Invalid configuration: {e}")
        
        # Save resolved configuration if requested
        if output_dir:
            self._save_resolved_config(config, resolved_dict, output_dir)
        
        return config
    
    def _execute_environment_setup(self, setup_config: dict[str, str], base_dir: Path) -> None:
        """Execute environment setup scripts"""
        logger.info("Executing environment setup scripts...")
        
        for executor, script_path in setup_config.items():
            script_full_path = (base_dir / script_path).resolve()
            
            if not script_full_path.exists():
                logger.warning(f"Setup script not found: {script_full_path}")
                continue
            
            logger.info(f"Running: {executor} {script_full_path}")
            
            try:
                # Run script and capture output
                result = subprocess.run(
                    [executor, str(script_full_path)],
                    capture_output=True,
                    text=True,
                    cwd=base_dir,
                    check=True
                )
                
                # Parse KEY=VALUE from output
                for line in result.stdout.splitlines():
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
                        
            except subprocess.CalledProcessError as e:
                logger.error(f"Setup script failed: {e.stderr}")
                raise RuntimeError(f"Environment setup failed: {script_path}")
    
    def _save_resolved_config(self, config: ProjectConfiguration, 
                            raw_dict: dict[str, Any], output_dir: Path) -> None:
        """Save resolved configuration as JSON for TCL scripts"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON for TCL scripts
        json_path = output_dir / "hdlproject_config_resolved.json"
        with open(json_path, 'w') as f:
            f.write(config.to_json(indent=2))
        logger.info(f"Saved resolved configuration: {json_path}")