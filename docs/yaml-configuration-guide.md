# YAML Configuration Guide

This document describes the structure and options for HDL project configuration files.

*Auto-generated from Pydantic models. Do not edit manually.*

## Contents

1. [Overview](#overview)
2. [Inheritance](#inheritance)
3. [Environment Variables](#environment-variables)
4. [Configuration Reference](#configuration-reference)
   - [ProjectConfiguration](#projectconfiguration)
   - [ProjectInformation](#projectinformation)
   - [DeviceInfo](#deviceinfo)
   - [Generic](#generic)
   - [Constraint](#constraint)
   - [BlockDesign](#blockdesign)
5. [Vivado Property Mapping](#vivado-property-mapping)

## Overview

Configuration files use YAML format and define all settings for an HDL project,
including device targeting, source files, constraints, and synthesis/implementation options.

The root element is `ProjectConfiguration`, which contains all other configuration sections.

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

The `inherits` key is processed before validation and removed from the final configuration.

## Environment Variables

All string values support environment variable substitution using `${VAR}` syntax:

```yaml
project_information:
  project_name: ${PROJECT_PREFIX}_design
  top_level_file_name: ${TOP_MODULE}.vhd
```

Variables are expanded at configuration load time. If a variable is not set,
the placeholder remains unchanged.

Environment variables can also be set via `environment_setup` scripts (see below).

## Configuration Reference

### ProjectConfiguration

Root configuration model for HDL projects.

    This is the top-level model that represents a complete project configuration file.
    Supports inheritance via the 'inherits' key (processed before model validation).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_information` | [ProjectInformation](#projectinformation) | Yes | `—` | Core project identification and settings. Required. |
| `hdldepends_config` | str | No | `null` | Path to hdldepends configuration file, relative to the project directory. Overrides default dependency resolution settings. |
| `constraints` | list[[Constraint](#constraint)] | No | `[]` | List of constraint files to include in the project. |
| `block_designs` | list[[BlockDesign](#blockdesign)] | No | `[]` | List of block designs to include in the project. |
| `synth_options` | dict[str, str] | No | `{}` | Vivado synthesis options. Keys are property names (e.g., STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY), values are property values. Maps to set_property -name <key> -value <value>. |
| `impl_options` | dict[str, str] | No | `{}` | Vivado implementation options. Keys are property names (e.g., STEPS.OPT_DESIGN.ARGS.DIRECTIVE), values are property values. Maps to set_property -name <key> -value <value>. |
| `environment_setup` | dict[str, str] | No | `null` | Scripts to execute before processing. Keys are executors (e.g., bash, python), values are script paths relative to the config file. Script output lines in KEY=VALUE format are added to environment. |
| `hdlproject_config_version` | str | No | `'3.0.0'` | Configuration schema version for compatibility checking. |

### ProjectInformation

Core project identification and settings.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_name` | str | Yes | `—` | Name of the Vivado project. Used for project directory and output file naming. |
| `top_level_file_name` | str | Yes | `—` | Filename of the top-level HDL module (without path). Must exist in the source file list. |
| `device_info` | [DeviceInfo](#deviceinfo) | Yes | `—` | FPGA device and board configuration. |
| `top_level_generics` | dict[str, [Generic](#generic)] | No | `{}` | Generic parameters to pass to the top-level module. Keys are generic names, values are Generic objects. |
| `vivado_version_year` | str | No | `null` | Vivado version year. Overrides device_info.vivado_version_year if both are specified. |
| `vivado_version_sub` | str | No | `null` | Vivado version sub-release. Overrides device_info.vivado_version_sub if both are specified. |

### DeviceInfo

FPGA device and board configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `part_name` | str | Yes | `—` | Xilinx FPGA part number. Must be a valid Xilinx part (e.g., xc7a35tcpg236-1, xczu9eg-ffvb1156-2-e). |
| `board_name` | str | Yes | `—` | Human-readable board name for identification purposes. |
| `board_part` | str | No | `null` | Xilinx board part identifier. Must be a valid Xilinx board part if specified (e.g., digilentinc.com:arty-a7-35:part0:1.1). |
| `vivado_version_year` | str | No | `null` | Vivado version year (e.g., 2023). Can be specified here or at project level. |
| `vivado_version_sub` | str | No | `null` | Vivado version sub-release (e.g., 1, 2). Can be specified here or at project level. |

### Generic

HDL generic/parameter definition for top-level module.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | str | Yes | `—` | VHDL type of the generic (e.g., integer, std_logic, std_logic_vector). |
| `value` | str | int | float | bool | No | `null` | Value to assign to the generic. Type must be compatible with the declared type. |

### Constraint

Constraint file configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | str | Yes | `—` | Path to the constraint file (.xdc), relative to the configuration file location. |
| `fileset` | str | No | `null` | Target fileset for the constraint (e.g., constrs_1). Defaults to the project's main constraint fileset. |
| `execution` | str | No | `null` | When the constraint should be applied: 'synthesis', 'implementation', or both if not specified. |
| `properties` | list[dict[str, str]] | dict[str, str] | No | `null` | Additional Vivado properties to set on the constraint file. Can be a single dict or list of dicts with property name-value pairs. |

### BlockDesign

Block design configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | str | Yes | `—` | Path to the block design file (.tcl or .bd), relative to the configuration file location. |
| `commands` | list[str] | No | `null` | Additional TCL commands to execute after loading the block design. |

## Vivado Property Mapping

The `synth_options` and `impl_options` fields map directly to Vivado `set_property` commands:

```yaml
synth_options:
  "STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY": "rebuilt"
  "STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS": "-mode out_of_context"

impl_options:
  "STEPS.OPT_DESIGN.ARGS.DIRECTIVE": "Explore"
  "STEPS.PLACE_DESIGN.ARGS.DIRECTIVE": "ExtraNetDelay_high"
```

Each entry generates a TCL command:

```tcl
set_property -name STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY -value rebuilt -objects [get_runs synth_1]
```

Refer to Vivado documentation for available property names and values.
