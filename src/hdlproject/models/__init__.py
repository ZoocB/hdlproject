# models/__init__.py

from hdlproject.models.models import (
    FlexibleModel,
    VivadoVersion,
    ToolExecutor,
    VivadoExecutor,  # backwards-compatible alias for ToolExecutor
    GlobalConfiguration,
    DeviceInfo,
    Generic,
    ProjectInformation,
    Constraint,
    BlockDesign,
    WriteHwPlatformOptions,
    BuildConfiguration,
    ProjectConfiguration,
)
from hdlproject.models.resolved import (
    ResolvedProjectConfig,
    ResolvedPaths,
    ResolvedOperationPaths,
)

__all__ = [
    "FlexibleModel",
    "VivadoVersion",
    "ToolExecutor",
    "VivadoExecutor",
    "GlobalConfiguration",
    "DeviceInfo",
    "Generic",
    "ProjectInformation",
    "Constraint",
    "BlockDesign",
    "WriteHwPlatformOptions",
    "BuildConfiguration",
    "ProjectConfiguration",
    "ResolvedProjectConfig",
    "ResolvedPaths",
    "ResolvedOperationPaths",
]
