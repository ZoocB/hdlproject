# config/project_config.py
"""Simplified project configuration"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from hdlproject.models.models import ProjectConfiguration as PydanticConfig
from hdlproject.config.config_resolver import ConfigResolver
from hdlproject.utils.logging_manager import get_logger
from hdlproject.config.paths import OperationPaths

logger = get_logger(__name__)


@dataclass
class VivadoVersion:
    """Vivado version information"""
    year: str
    sub: str
    settings_path: Path
    
    @property
    def full_version(self) -> str:
        return f"{self.year}.{self.sub}"
    
    def __str__(self) -> str:
        return self.full_version


@dataclass
class ProjectConfig:
    """
    Unified project configuration with clear directory naming.
    """
    # Required fields
    name: str
    project_dir: Path  # The individual project directory
    repository_root: Path  # The git repository root directory
    configuration_path: Path
    
    # Device information
    device_part: str
    board_name: str
    
    # Design information
    top_level_file_name: str
    
    # Optional fields
    board_part: Optional[str] = None
    top_level_file_path: Optional[Path] = None
    top_level_generics: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Design components
    constraints: list[dict[str, Any]] = field(default_factory=list)
    block_designs: list[dict[str, Any]] = field(default_factory=list)
    
    # Build options
    synthesis_options: dict[str, Any] = field(default_factory=dict)
    implementation_options: dict[str, Any] = field(default_factory=dict)
    
    # Resolved configuration path
    resolved_configuration_path: Optional[Path] = None
    
    # Fields not part of __init__
    vivado_version: VivadoVersion = field(init=False)
    _pydantic_model: Optional[PydanticConfig] = field(default=None, init=False, repr=False)
    
    @classmethod
    def load_from_yaml(
        cls,
        project_name: str,
        projects_base_dir: Path,
        vivado_location: Path,
        repository_root: Path,
        check_if_vivado_version_exists: bool = True

    ) -> 'ProjectConfig':
        """
        Load project configuration from YAML file.
        
        Args:
            project_name: Name of the project
            projects_base_dir: Base directory containing all projects
            vivado_location: Vivado installation location
            repository_root: Git repository root directory
            
        Returns:
            Loaded and validated ProjectConfig
        """
        project_dir = projects_base_dir / project_name
        
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")
        
        # Find configuration file
        config_path = cls._find_configuration_file(project_dir)
        if not config_path:
            raise FileNotFoundError(
                f"No configuration file found for project '{project_name}' in {project_dir}"
            )
        
        # Create resolver and load configuration
        resolver = ConfigResolver(projects_base_dir)
        
        try:
            # This loads and validates the YAML, returning a Pydantic model
            pydantic_config = resolver.resolve_config(config_path)
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            raise RuntimeError(f"Failed to load configuration: {e}")
        
        # Extract information from pydantic model
        project_info = pydantic_config.project_information
        device_info = project_info.device_info
        
        # Create ProjectConfig instance
        config = cls(
            name=project_name,
            project_dir=project_dir,
            repository_root=repository_root,
            configuration_path=config_path,
            device_part=device_info.part_name,
            board_name=device_info.board_name,
            board_part=device_info.board_part,
            top_level_file_name=project_info.top_level_file_name,
            top_level_generics={
                name: generic.model_dump(exclude_unset=True)
                for name, generic in project_info.top_level_generics.items()
            },
            constraints=[c.model_dump() for c in pydantic_config.constraints],
            block_designs=[bd.model_dump() for bd in pydantic_config.block_designs],
            synthesis_options=pydantic_config.synth_options,
            implementation_options=pydantic_config.impl_options
        )
        
        config._pydantic_model = pydantic_config
        
        # Get Vivado version and settings
        vivado_year, vivado_sub = project_info.get_vivado_version()
        config._set_vivado_version(vivado_year, vivado_sub, vivado_location, check_if_vivado_version_exists)
        
        # Find top-level file
        config.top_level_file_path = config._find_top_level_file(repository_root)
        
        return config
    
    def resolve_for_operation(self, operation: str, output_directory: Path) -> None:
        """
        Resolve configuration for a specific operation.
        
        Args:
            operation: Operation name (e.g., 'build', 'open')
            output_directory: Directory to save resolved configuration
        """
        if not self._pydantic_model:
            raise RuntimeError("Configuration not loaded")
        
        # Save resolved configuration as JSON for TCL scripts
        self.resolved_configuration_path = output_directory / "hdlproject_config_resolved.json"
        self.resolved_configuration_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.resolved_configuration_path, 'w') as f:
            f.write(self._pydantic_model.to_json(indent=2))
        
        logger.info(f"Resolved configuration saved to: {self.resolved_configuration_path}")
    
    def get_operation_paths(self, operation: str) -> OperationPaths:
        """Get standardised paths for an operation"""
        # Use hidden directories with clear naming
        hdlproject_dir = self.project_dir / ".hdlproject-vivado"
        operation_dir = hdlproject_dir / operation
        
        return OperationPaths(
            operation_dir=operation_dir,
            logs_dir=operation_dir / "logs",
            project_dir=operation_dir / "project",
            bd_dir=operation_dir / "bd",
            xci_dir=operation_dir / "xci"
        )
    
    def validate(self, check_vivado: bool = True) -> list[str]:
        """
        Validate project configuration.
        
        Args:
            check_vivado: Whether to validate Vivado installation (default: True)
        
        Returns:
            list of validation errors (empty if valid)
        """
        errors = []
        
        # Check project directory
        if not self.project_dir.exists():
            errors.append(
                f"Project directory not found: {self.project_dir}\n"
                f"  - Check that the project name is correct\n"
                f"  - Verify the project_dir setting in hdlproject-config.json"
            )
        
        # Check Vivado settings (optional)
        if check_vivado and not self.vivado_version.settings_path.exists():
            errors.append(
                f"Vivado {self.vivado_version.full_version} not found at: {self.vivado_version.settings_path}\n"
                f"  - Install Vivado {self.vivado_version.full_version}\n"
                f"  - Or update vivado_version in project configuration\n"
                f"  - Available versions: {self._list_available_vivado_versions()}"
            )
        
        # Check top-level file
        if not self.top_level_file_path:
            errors.append(f"Top-level file '{self.top_level_file_name}' not found in repository")
        elif not self.top_level_file_path.exists():
            errors.append(f"Top-level file not found at: {self.top_level_file_path}")
        
        # Check resolved configuration
        if self.resolved_configuration_path and not self.resolved_configuration_path.exists():
            errors.append(f"Resolved configuration not found: {self.resolved_configuration_path}")
        
        return errors
    
    def validate_or_raise(self) -> None:
        """Validate and raise exception if invalid"""
        errors = self.validate()
        if errors:
            error_msg = f"Project configuration validation failed for '{self.name}':\n"
            error_msg += "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_msg)
    
    def get_tcl_arguments(self, mode: str, operation_paths: OperationPaths, cores: int = 1) -> list[str]:
        """Get TCL script arguments"""
        if not self.resolved_configuration_path:
            raise RuntimeError("Configuration not resolved for operation")
        
        return [
            '--mode', mode,
            '--vivado-project-dir', str(operation_paths.project_dir),
            '--project-root', str(self.project_dir),
            '--cores', str(cores),
            '--config', str(self.resolved_configuration_path)
        ]
    
    @staticmethod
    def _find_configuration_file(directory: Path) -> Optional[Path]:
        """Find YAML configuration file in directory"""
        for name in ['hdlproject_config.yaml', 'hdlproject_config.yml']:
            path = directory / name
            if path.exists():
                return path
        return None
    
    def _find_top_level_file(self, repository_root: Path) -> Optional[Path]:
        """Find top-level HDL file in repository"""
        extensions = ['.vhd', '.vhdl', '.v', '.sv']
        found_files = []
        
        for ext in extensions:
            pattern = f"{self.top_level_file_name}{ext}"
            found_files.extend(repository_root.rglob(pattern))
        
        if not found_files:
            logger.warning(f"Top-level file '{self.top_level_file_name}' not found in {repository_root}")
            return None
        
        if len(found_files) > 1:
            logger.warning(f"Multiple files found for '{self.top_level_file_name}': {found_files}")
            # Use the first one but log warning
            return found_files[0]
        
        return found_files[0]
    
    def _set_vivado_version(self, year: str, sub: str, vivado_location: Path, check_if_vivado_version_exists:bool=True) -> None:
        """Set Vivado version information"""
        settings_path = vivado_location / f"{year}.{sub}" / "settings64.sh"
        
        if check_if_vivado_version_exists:
            if not settings_path.exists():
                raise FileNotFoundError(f"Vivado {year}.{sub} not found at {settings_path}")
        
        self.vivado_version = VivadoVersion(
            year=year,
            sub=sub,
            settings_path=settings_path
        )