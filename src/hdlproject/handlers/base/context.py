# handlers/base/context.py
"""Execution context objects for handler execution"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from hdlproject.config.project_config import ProjectConfig
from hdlproject.config.paths import OperationPaths


@dataclass
class ProjectContext:
    """Everything about a single project for this execution"""
    config: ProjectConfig
    operation_paths: OperationPaths
    compile_order_path: Optional[Path] = None


@dataclass
class ExecutionContext:
    """Everything needed for handler execution across all projects"""
    projects: list[ProjectContext]
    options: Any                        # Handler-specific options (BuildOptions, etc.)
    operation_config: Any               # OperationConfig from handler
    environment: dict[str, Any]         # Shared environment (project_dir, etc.)
    
    # Services available to handlers
    vivado_executor: Any
    status_manager: Any
    compile_order_service: Any


@dataclass
class SingleProjectContext:
    """Context for processing a single project"""
    project: ProjectContext
    options: Any
    operation_config: Any
    vivado_executor: Any
    status_manager: Any
    compile_order_service: Any