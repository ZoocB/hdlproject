# core/compile_order.py
"""Compile order generation using hdldepends command"""

import subprocess
import shutil
import os
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
    
    def __init__(self, 
                 output_format: str = "json",
                 hdldepends_config_path: Path = None):
        """
        Initialise compile order manager.
        
        Args:
            output_format: Output format for compile order file (txt, csv, json)
            hdldepends_config_path: Path to hdldepends configuration file (required)
            
        Raises:
            ValueError: If hdldepends_config_path not provided or invalid
            FileNotFoundError: If hdldepends config file doesn't exist
            RuntimeError: If hdldepends command is not found in PATH
        """
        if hdldepends_config_path is None:
            raise ValueError(
                "hdldepends_config_path is required. "
                "Specify in hdlproject_global_config.yaml or project config."
            )
        
        if not hdldepends_config_path.exists():
            raise FileNotFoundError(
                f"HDLDepends configuration file not found: {hdldepends_config_path}"
            )
        
        # Validate file extension
        valid_extensions = ['.json', '.toml']
        if hdldepends_config_path.suffix not in valid_extensions:
            raise ValueError(
                f"Invalid hdldepends config extension: {hdldepends_config_path.suffix}\n"
                f"  Must be one of: {valid_extensions}"
            )
        
        if output_format not in ["txt", "csv", "json"]:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        self.output_format = output_format
        self.hdldepends_config_path = hdldepends_config_path
        
        # Validate hdldepends is available
        if not shutil.which('hdldepends'):
            raise RuntimeError(
                "hdldepends command not found in PATH. "
                "Please install hdldepends package:\n"
                "  pip install hdldepends"
            )
        
        logger.info(f"Using hdldepends configuration: {hdldepends_config_path}")
        logger.debug(f"Compile order manager initialised with format: {output_format}")

    def generate(self, 
                root_dir: Path, 
                top_level_file: str, 
                working_dir: Path,
                vivado_version: Optional[str] = None,
                device_part: Optional[str] = None,
                env: Optional[dict] = None) -> Path:
        """
        Generate compile order file using hdldepends.
        
        Args:
            root_dir: Repository root directory
            top_level_file: Path to the top-level HDL file
            working_dir: Directory where compile order file will be created
            vivado_version: Vivado version string (e.g., "2021.1")
            device_part: Device part number (e.g., "xczu43dr-ffvg1517-2-i")
            env: Environment variables to use (should include XILINX_VIVADO)
            
        Returns:
            Path to generated compile order file
            
        Raises:
            RuntimeError: If hdldepends execution fails
        """
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Build output file path
        output_file = working_dir / f"compile_order.{self.output_format}"
        
        # Build command using hdldepends from PATH
        command = [
            "hdldepends",
            "--top-file", top_level_file,
            "--compile-order-json", str(output_file),
            "--no-pickle",
            "-vv"
        ]
        
        # Add tool-specific arguments if provided
        if vivado_version:
            command.extend(["--x-tool-version", vivado_version])
        
        if device_part:
            command.extend(["--x-device", device_part])
        
        # Add config file at the end
        command.append(str(self.hdldepends_config_path))
        
        logger.info(f"Running hdldepends: {' '.join(command)}")
        
        # Use provided environment or fall back to current environment
        if env is None:
            env = os.environ.copy()
        
        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True,
                env=env
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