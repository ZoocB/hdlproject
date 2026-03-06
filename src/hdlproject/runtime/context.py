"""Runtime context objects for handler execution.

This module contains runtime state objects used during handler execution.
The ResolvedProjectConfig (from models.resolved) is the primary configuration
carrier. This module provides execution context wrappers.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hdlproject.models.models import GlobalConfiguration
    from hdlproject.models.resolved import ResolvedProjectConfig, ResolvedOperationPaths


# =============================================================================
# Runtime Environment
# =============================================================================


@dataclass
class RuntimeEnvironment:
    """Global runtime environment, created once per CLI invocation.

    This is shared (read-only) across all projects being processed.
    Contains the global configuration and repository-level paths.
    """

    repository_root: Path
    global_config: "GlobalConfiguration"
    vivado_location: Optional[Path] = None  # For validation only, not execution

    @property
    def projects_base_dir(self) -> Path:
        """Get the base directory containing all projects."""
        return self.repository_root / self.global_config.project_dir


# =============================================================================
# Execution Contexts
# =============================================================================


@dataclass
class ExecutionServices:
    """Services available to handlers during execution.

    These are stateless services that can be safely shared across threads.
    """

    vivado_executor: Any  # VivadoExecutorService
    status_manager: Any  # StatusManager
    compile_order_service: Any  # CompileOrderService (can be None)


@dataclass
class ExecutionContext:
    """Context for handler execution across all projects.

    Passed to handler.configure() and used for orchestration.
    """

    environment: RuntimeEnvironment
    resolved_configs: list["ResolvedProjectConfig"]
    handler_options: Any  # BuildHandlerOptions, ExportHandlerOptions, etc.
    operation_config: Any  # OperationConfig from handler
    services: ExecutionServices


@dataclass
class SingleProjectExecution:
    """Context for processing a single project.

    Passed to handler.prepare() and handler.execute_single().
    Each parallel worker gets its own instance.
    """

    resolved_config: "ResolvedProjectConfig"
    operation_paths: "ResolvedOperationPaths"
    handler_options: Any
    operation_config: Any
    services: ExecutionServices

    @property
    def project_name(self) -> str:
        """Convenience access to project name."""
        return self.resolved_config.project_name
