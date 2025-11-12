"""Resource management utilities for accessing package data files"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional
from importlib.resources import files, as_file

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ResourceManager:
    """Manages access to package resources (TCL scripts)"""
    
    def __init__(self):
        self._temp_dirs = []
    
    def get_tcl_script_path(self, script_name: str) -> Path:
        """
        Get path to a TCL script. Extracts to temp directory to allow
        TCL scripts to source each other.
        
        Args:
            script_name: Name of the TCL script
            
        Returns:
            Path to the TCL script in temporary directory
        """
        tcl_files = files('hdlproject.tcl')
        
        # Create temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix='hdlproject_tcl_'))
        self._temp_dirs.append(temp_dir)
        
        # Extract all TCL scripts
        for resource in tcl_files.iterdir():
            if resource.name.endswith('.tcl'):
                with as_file(resource) as resource_path:
                    dest = temp_dir / resource.name
                    shutil.copy2(resource_path, dest)
                    logger.debug(f"Extracted TCL: {resource.name}")
        
        script_path = temp_dir / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"TCL script not found: {script_name}")
        
        logger.debug(f"Using TCL script: {script_path}")
        return script_path
    
    def cleanup(self):
        """Clean up temporary directories"""
        for temp_dir in self._temp_dirs:
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {temp_dir}: {e}")
        self._temp_dirs.clear()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.cleanup()


# Global resource manager
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def get_tcl_script(script_name: str) -> Path:
    """Get a TCL script path"""
    return get_resource_manager().get_tcl_script_path(script_name)