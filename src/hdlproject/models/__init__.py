"""
# YAML Configuration Guide

This document describes the structure and options for HDL project configuration files.

*Auto-generated from Pydantic models. Do not edit manually.*

## Configuration Files

There are two types of configuration files:

- **Global Configuration** (`hdlproject_global_config.yaml`): Located at
  repository root, defines repository-wide settings
- **Project Configuration** (`hdlproject_project_config.yaml`): Located in
  each project directory, defines project-specific settings

Project-level settings override global settings where noted.

## Inheritance

Configuration files support inheritance via the `inherits` key:

```yaml
inherits: base-config.yaml
# or multiple parents:
inherits:
  - base-config.yaml
  - device-config.yaml
```

**Merge behaviour:**

| Type | Behaviour |
|------|-----------|
| Lists | Appended (parent items first, then child items) |
| Dicts | Recursively merged |
| Scalars | Error if defined in both parent and child |
"""

from hdlproject.models.base import FlexibleModel
from hdlproject.models.build import (
    BlockDesign,
    BuildConfiguration,
    BuildVariable,
    Constraint,
    GeneratedSource,
    HooksConfig,
    WriteHwPlatformOptions,
)
from hdlproject.models.device import DeviceInfo, ProjectInformation
from hdlproject.models.global_config import GlobalConfiguration
from hdlproject.models.project_config import ProjectConfiguration
from hdlproject.models.resolved import (
    ResolvedOperationPaths,
    ResolvedPaths,
    ResolvedProjectConfig,
)
from hdlproject.models.tool import ShellConfig, ToolExecutor, VivadoVersion

# The user-facing configuration schema, in a stable order. This is the single
# source of truth for documentation generation (see scripts/generate_docs.py),
# replacing reflection over a single monolithic module.
CONFIG_MODELS = [
    VivadoVersion,
    ShellConfig,
    ToolExecutor,
    GlobalConfiguration,
    DeviceInfo,
    ProjectInformation,
    Constraint,
    BlockDesign,
    BuildVariable,
    GeneratedSource,
    WriteHwPlatformOptions,
    BuildConfiguration,
    HooksConfig,
    ProjectConfiguration,
]

__all__ = [
    "FlexibleModel",
    "VivadoVersion",
    "ShellConfig",
    "ToolExecutor",
    "GlobalConfiguration",
    "DeviceInfo",
    "ProjectInformation",
    "Constraint",
    "BlockDesign",
    "BuildVariable",
    "GeneratedSource",
    "WriteHwPlatformOptions",
    "BuildConfiguration",
    "HooksConfig",
    "ProjectConfiguration",
    "ResolvedProjectConfig",
    "ResolvedPaths",
    "ResolvedOperationPaths",
    "CONFIG_MODELS",
]
