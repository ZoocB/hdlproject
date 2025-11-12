# core/compile_order.py
"""Compile order generation using hdldepends command"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class CompileOrderManager:
    """
    Manages compile order generation using hdldepends command.
    
    Requires hdldepends to be installed and available in PATH:
        pip install hdldepends
    """
    
    def __init__(self, output_format: str = "json"):
        """
        Initialise compile order manager.
        
        Args:
            output_format: Output format for compile order file (txt, csv, json)
            
        Raises:
            RuntimeError: If hdldepends command is not found in PATH
        """
        
        self.output_format = output_format
        
        if output_format not in ["txt", "csv", "json"]:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        # Validate hdldepends is available
        if not shutil.which('hdldepends'):
            raise RuntimeError(
                "hdldepends command not found in PATH. "
                "Please install hdldepends package in virtual environment:\n"
                "  pip install hdldepends"
            )
        
        logger.debug(f"Compile order manager Initialised with format: {output_format}")
    
    def generate(self, root_dir: Path, top_level_file: str, working_dir: Path) -> Optional[Path]:
        """
        Generate compile order file using hdldepends.
        
        Args:
            root_dir: Repository root directory (where hdldepends config is located)
            top_level_file: Path to the top-level HDL file
            working_dir: Directory where compile order file will be created
            
        Returns:
            Path to generated compile order file, or None if config not found
            
        Raises:
            RuntimeError: If hdldepends execution fails
        """
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Find HDLDepends configuration
        config_file = self._find_hdldepends_config(root_dir)
        if not config_file:
            logger.warning(
                f"HDLDepends configuration not found in {root_dir}, "
                "skipping compile order generation"
            )
            return None
        
        # Build command using hdldepends from PATH
        output_file = working_dir / f"compile_order.{self.output_format}"
        
        command = [
            "hdldepends",
            "--top-file", top_level_file,
            "--compile-order-json", str(output_file),
            "--no-pickle",
            "-vv",
            str(config_file)
        ]
        
        logger.info(f"Running hdldepends: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            if result.stdout:
                logger.debug(f"hdldepends output:\n{result.stdout}")
            
            if not output_file.exists():
                raise RuntimeError(
                    f"hdldepends did not create output file: {output_file}"
                )
            
            logger.info(f"Generated compile order: {output_file}")
            return output_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"hdldepends failed with exit code {e.returncode}")
            if e.stderr:
                logger.error(f"stderr: {e.stderr}")
            raise RuntimeError(f"Compile order generation failed: {e.stderr}") from e
        except Exception as e:
            logger.error(f"Unexpected error during compile order generation: {e}")
            raise
    
    def _find_hdldepends_config(self, root_dir: Path) -> Optional[Path]:
        """
        Find HDLDepends configuration file in repository root.
        
        Searches for:
            - hdldepends.json
            - hdldepends.toml
            
        Args:
            root_dir: Directory to search for config file
            
        Returns:
            Path to config file if found, None otherwise
        """
        for config_name in ["hdldepends.json", "hdldepends.toml"]:
            config_path = root_dir / config_name
            if config_path.exists():
                logger.debug(f"Found HDLDepends config: {config_path}")
                return config_path
        
        return None