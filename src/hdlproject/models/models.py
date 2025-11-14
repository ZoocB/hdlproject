# models/models.py
"""Simplified Pydantic models for project configuration"""

from typing import Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
import os
import re


class FlexibleModel(BaseModel):
    """Base model that allows extra fields and does env var substitution"""
    model_config = ConfigDict(
        extra='allow',
        validate_assignment=True,
        str_strip_whitespace=True
    )
    
    @field_validator('*', mode='before')
    @classmethod
    def substitute_env_vars(cls, v: Any) -> Any:
        """Replace ${VAR} with environment variable values"""
        if isinstance(v, str):
            return re.sub(
                r'\$\{([A-Z_][A-Z0-9_]*)\}',
                lambda m: os.environ.get(m.group(1), m.group(0)),
                v
            )
        elif isinstance(v, dict):
            return {k: cls.substitute_env_vars(val) for k, val in v.items()}
        elif isinstance(v, list):
            return [cls.substitute_env_vars(item) for item in v]
        return v


class DeviceInfo(FlexibleModel):
    """FPGA device information"""
    part_name: str
    board_name: str
    board_part: Optional[str] = None
    vivado_version_year: Optional[str] = None
    vivado_version_sub: Optional[str] = None


class Generic(FlexibleModel):
    """Generic parameter"""
    type: str
    value: Optional[Union[str, int, float, bool]] = None


class Constraint(FlexibleModel):
    """Constraint file"""
    file: str
    fileset: Optional[str] = None
    execution: Optional[str] = None
    properties: Optional[Union[list[dict[str, str]], dict[str, str]]] = None
    
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override to ensure properties are in the right format"""
        data = super().model_dump(**kwargs)
        # Normalise properties to list format if needed
        if 'properties' in data and isinstance(data['properties'], dict):
            data['properties'] = [data['properties']]
        return data


class BlockDesign(FlexibleModel):
    """Block design"""
    name: str


class ProjectInformation(FlexibleModel):
    """Project information"""
    project_name: str
    top_level_file_name: str
    device_info: DeviceInfo
    top_level_generics: dict[str, Generic] = Field(default_factory=dict)
    vivado_version_year: Optional[str] = None
    vivado_version_sub: Optional[str] = None
    
    def get_vivado_version(self) -> tuple[str, str]:
        """Get Vivado version from either location"""
        year = self.vivado_version_year or self.device_info.vivado_version_year
        sub = self.vivado_version_sub or self.device_info.vivado_version_sub
        
        if not year or not sub:
            raise ValueError("Vivado version not specified")
        
        return year, sub


class ProjectConfiguration(FlexibleModel):
    """Main configuration"""
    project_information: ProjectInformation
    
    # Optional project-level override for hdldepends config
    # Path is relative to the project directory
    hdldepends_config: Optional[str] = None
    
    constraints: list[Constraint] = Field(default_factory=list)
    block_designs: list[BlockDesign] = Field(default_factory=list)
    synth_options: dict[str, Any] = Field(default_factory=dict)
    impl_options: dict[str, Any] = Field(default_factory=dict)
    environment_setup: Optional[dict[str, str]] = None
    
    # Version for compatibility
    hdlproject_config_version: Optional[str] = Field("3.0.0", description="Configuration version")
    
    def to_json_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return self.model_dump(exclude_unset=True, exclude_none=True)
    
    def to_json(self, **kwargs) -> str:
        """Convert to JSON string"""
        import json
        data = self.to_json_dict()
        return json.dumps(data, **kwargs)