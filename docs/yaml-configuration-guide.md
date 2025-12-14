# YAML Configuration Guide

This document describes the structure and options for HDL project configuration files.

*Auto-generated from Pydantic models. Do not edit manually.*

## Configuration Files

There are two types of configuration files:

- **Global Configuration** (`hdlproject_global_config.yaml`): Located at repository root, defines repository-wide settings
- **Project Configuration** (`hdlproject_project_config.yaml`): Located in each project directory, defines project-specific settings

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

## Contents

- [Configuration Files](#configuration-files)
- [Inheritance](#inheritance)
- [Configuration Reference](#configuration-reference)
  - [BlockDesign](#blockdesign)
  - [WriteHwPlatformOptions](#writehwplatformoptions)
  - [BuildConfiguration](#buildconfiguration)
  - [Constraint](#constraint)
  - [DeviceInfo](#deviceinfo)
  - [Generic](#generic)
  - [ShellConfig](#shellconfig)
  - [VivadoExecutor](#vivadoexecutor)
  - [GlobalConfiguration](#globalconfiguration)
  - [VivadoVersion](#vivadoversion)
  - [ProjectInformation](#projectinformation)
  - [ProjectConfiguration](#projectconfiguration)
- [Complete Examples](#complete-examples)

## Configuration Reference

### BlockDesign

Block design configuration.

Example:
```yaml
block_designs:
  - file: processing_system.bd
    commands:
      - "regenerate_bd_layout"
      - "validate_bd_design"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | str | Yes | `—` | Path to block design file (.tcl or .bd), relative to config file. |
| `commands` | list[str] | No | `null` | Additional TCL commands to execute after loading. |

### WriteHwPlatformOptions

Options for write_hw_platform Vivado command.

Example:
```yaml
build_configuration:
  write_hw_platform:
    include_bit: true
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `include_bit` | bool | No | `False` | Include bitstream in hardware platform file (.xsa). |

### BuildConfiguration

Build-time configuration for synthesis and implementation.

These are persistent options stored in the config, distinct from
CLI runtime options like --cores or --clean.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `write_hw_platform` | [WriteHwPlatformOptions](#writehwplatformoptions) | No | `WriteHwPlatformOptions(include_bit=False)` | Options for hardware platform file (.xsa) generation. |

### Constraint

Constraint file configuration.

Example:
```yaml
constraints:
  - file: timing.xdc
  - file: pins.xdc
    fileset: constrs_1
  - file: debug.xdc
    execution: immediate
    properties:
      USED_IN_SYNTHESIS: false
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | str | Yes | `—` | Path to constraint file (.xdc), relative to config file. |
| `fileset` | str | No | `null` | Target fileset (e.g., constrs_1). Defaults to main constraint fileset. |
| `execution` | str | No | `null` | Options: `immediate` - Executes the script immediate upon processing it and doesnt add it to the project. |
| `properties` | list[dict[str, str]] | dict[str, str] | No | `null` | Additional Vivado properties for the constraint file. |

### DeviceInfo

FPGA device and board configuration.

Example:
```yaml
device_info:
  part_name: xc7z020clg400-1
  board_name: Arty_Z7_20
  board_part: digilentinc.com:arty-z7-20:part0:1.1
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `part_name` | str | Yes | `—` | Xilinx FPGA part number (e.g., xc7a35tcpg236-1). |
| `board_name` | str | Yes | `—` | Human-readable board name for identification. |
| `board_part` | str | No | `null` | Xilinx board part identifier (e.g., digilentinc.com:arty-a7-35:part0:1.1). |

### Generic

HDL generic/parameter for top-level module.

Example:
```yaml
top_level_generics:
  DATA_WIDTH:
    type: integer
    value: 32
  ENABLE_DEBUG:
    type: std_logic
    value: '1'
  INIT_VECTOR:
    type: std_logic_vector
    width: 8
    value: "0xFF"
    format: hex
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `type` | str | Yes | `—` | VHDL type (e.g., integer, std_logic, std_logic_vector). |
| `value` | str | int | float | bool | No | `null` | Value to assign. Type must be compatible with declared type. |
| `width` | int | No | `null` | Bit width for vector types. |
| `format` | str | No | `null` | Value format hint ('hex', 'bin', 'dec'). |

### ShellConfig

Shell configuration for custom execution environments.

Used when commands need to run in a custom shell (e.g., Docker container).
When `heredoc` is true, commands are passed via stdin with `set -e` for
error handling.

Example:
```yaml
shell:
  invoke: "docker_tool vivado-2023.2"
  heredoc: true
  mount_repo_root: true
  options:
    - "--pull=never"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `invoke` | str | Yes | `—` | Command to start the shell (e.g., 'docker_tool vivado-2023.2') |
| `heredoc` | bool | No | `False` | Use heredoc/stdin mode. Commands passed via stdin with 'set -e'. |
| `mount_repo_root` | bool | No | `False` | Mount repository root into container. Adds '--volume {repo_root}:{repo_root}' to options. |
| `options` | list[str] | No | `[]` | Additional options passed to the shell command after '--'. For docker_tool: docker/podman options like '--pull=never'. |

### VivadoExecutor

Configuration for executing a specific Vivado version.

Defines how to execute Vivado and related tools (like hdldepends) for a
specific version. Supports both local installations and containerised
environments.

The execution flow is: [shell] → [setup] → [injected commands] → [executable]

Example:
```yaml
vivado_executors:
  # Local installation
  "2020.1":
    setup:
      - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"
    executable: "vivado"

  # Docker container with heredoc and repo mounting
  "2023.2":
    shell:
      invoke: "docker_tool vivado-2023.2"
      heredoc: true
      mount_repo_root: true
      options:
        - "--pull=never"
    setup:
      - "source /opt/Xilinx/Vivado/2023.2/settings64.sh"
      - 'REPO_ROOT="$(git rev-parse --show-toplevel)"'
      - 'source "${REPO_ROOT}/venv/bin/activate"'
    executable: "vivado"

  # Local with extra environment setup
  "2021.1":
    setup:
      - "source /tools/Xilinx/Vivado/2021.1/settings64.sh"
      - "export XILINX_LOCAL_USER_DATA=no"
    executable: "vivado"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `executable` | str | Yes | `—` | Command to invoke the tool (e.g., 'vivado') |
| `setup` | list[str] | No | `[]` | Setup commands to run first (e.g., source settings.sh). Executed before any injected commands like hdldepends. |
| `shell` | [ShellConfig](#shellconfig) | No | `null` | Custom shell configuration. If not set, uses /bin/bash with && chaining. Use this for Docker or other containerised environments. |

### GlobalConfiguration

Global repository configuration (`hdlproject_global_config.yaml`).

Located at repository root. Settings can be overridden at project level.

Example:
```yaml
project_dir: "fw/prj"
hdldepends_config: "hdldepends.json"
default_cores: 2
max_parallel_builds: 4
compile_order_format: "json"

vivado_executors:
  "2020.1":
    setup:
      - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"
    executable: "vivado"
  "2023.2":
    shell:
      invoke: "docker_tool vivado-2023.2"
      heredoc: true
    setup:
      - "source /opt/Xilinx/Vivado/2023.2/settings64.sh"
    executable: "vivado"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_dir` | str | Yes | `—` | Base directory containing project directories, relative to repository root. |
| `hdldepends_config` | str | No | `null` | Default hdldepends config path, relative to repository root. Overridable per-project. |
| `vivado_executors` | dict[str, [VivadoExecutor](#vivadoexecutor)] | No | `{}` | Vivado execution configs keyed by version (e.g., '2020.1'). Overridable per-project. |
| `default_cores` | int | No | `2` | Default CPU cores per project for synthesis/implementation. |
| `max_parallel_builds` | int | No | `null` | Maximum parallel builds. If None, calculated from system resources. |
| `compile_order_format` | str | No | `'json'` | Output format for compile order files ('json' or 'tcl'). |

### VivadoVersion

Vivado version specification.

Example:
```yaml
vivado_version:
  year: "2020"
  minor: "1"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `year` | str | Yes | `—` | Vivado version year (e.g., '2020', '2023'). |
| `minor` | str | Yes | `—` | Vivado version minor release (e.g., '1', '2'). |

### ProjectInformation

Core project identification and settings.

Example:
```yaml
project_information:
  project_name: my_project
  top_level_file_name: top_level
  device_info:
    part_name: xc7z020clg400-1
    board_name: Arty_Z7_20
  vivado_version:
    year: "2020"
    minor: "1"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_name` | str | Yes | `—` | Vivado project name. Used for .xpr file and output naming. |
| `top_level_file_name` | str | Yes | `—` | Top-level HDL module filename (without path or extension). |
| `device_info` | [DeviceInfo](#deviceinfo) | Yes | `—` | FPGA device and board configuration. |
| `vivado_version` | [VivadoVersion](#vivadoversion) | Yes | `—` | Vivado version to use for this project. |
| `top_level_generics` | dict[str, [Generic](#generic)] | No | `{}` | Generic parameters for top-level module. Keys are generic names. |

### ProjectConfiguration

Root project configuration (`hdlproject_project_config.yaml`).

Located in each project directory. This is the top-level model representing
a complete project configuration file.

Example for `synth_options` and `impl_options` - these map directly to
Vivado `set_property` commands:

```yaml
synth_options:
  STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY: rebuilt
  STEPS.SYNTH_DESIGN.ARGS.DIRECTIVE: AreaOptimized_high

impl_options:
  STEPS.OPT_DESIGN.ARGS.DIRECTIVE: Explore
  STEPS.PLACE_DESIGN.ARGS.DIRECTIVE: ExtraNetDelay_high
```

Each generates TCL like:
```tcl
set_property -name STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY -value rebuilt -objects [get_runs synth_1]
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_information` | [ProjectInformation](#projectinformation) | Yes | `—` | Core project identification and settings. |
| `hdldepends_config` | str | No | `null` | Project-specific hdldepends config path. Overrides global setting. |
| `vivado_executors` | dict[str, [VivadoExecutor](#vivadoexecutor)] | No | `null` | Project-specific Vivado executors. Overrides global settings. |
| `constraints` | list[[Constraint](#constraint)] | No | `[]` | Constraint files to include. |
| `block_designs` | list[[BlockDesign](#blockdesign)] | No | `[]` | Block designs to include. |
| `synth_options` | dict[str, str] | No | `{}` | Vivado synthesis properties (STEPS.SYNTH_DESIGN.ARGS.*). |
| `impl_options` | dict[str, str] | No | `{}` | Vivado implementation properties (STEPS.*.ARGS.*). |
| `build_configuration` | [BuildConfiguration](#buildconfiguration) | No | `BuildConfiguration(write_hw_platform=WriteHwPlatformOptions(include_bit=False))` | Build-time configuration options. |
| `environment_setup` | dict[str, str] | No | `null` | Pre-processing scripts. Keys: executor, Values: script path. Output KEY=VALUE lines added to env. |
| `hdlproject_config_version` | str | No | `'4.0.0'` | Configuration schema version. |

## Complete Examples

Auto-generated examples showing all fields with dummy values.

### Global Configuration Example

```yaml
project_dir: "my_project_dir_0"
hdldepends_config: "my_hdldepends_config_0"
vivado_executors:
  my_vivado_executors_key_0:
    executable: "my_executable_0"
    setup:
      - "my_setup_item_0"
      - "my_setup_item_1"
    shell:
      invoke: "my_invoke_0"
      heredoc: true
      mount_repo_root: true
      options:
        - "my_options_item_0"
        - "my_options_item_1"
  my_vivado_executors_key_1:
    executable: "my_executable_1"
    setup:
      - "my_setup_item_2"
      - "my_setup_item_3"
    shell:
      invoke: "my_invoke_1"
      heredoc: false
      mount_repo_root: false
      options:
        - "my_options_item_2"
        - "my_options_item_3"
default_cores: 0
max_parallel_builds: 0
compile_order_format: "my_compile_order_format_0"
```

### Project Configuration Example

```yaml
project_information:
  project_name: "my_project_name_0"
  top_level_file_name: "my_top_level_file_name_0"
  device_info:
    part_name: "my_part_name_0"
    board_name: "my_board_name_0"
    board_part: "my_board_part_0"
  vivado_version:
    year: "my_year_0"
    minor: "my_minor_0"
  top_level_generics:
    my_top_level_generics_key_0:
      type: "my_type_0"
      value: "my_value_0"
      width: 0
      format: "my_format_0"
    my_top_level_generics_key_1:
      type: "my_type_1"
      value: "my_value_1"
      width: 1
      format: "my_format_1"
hdldepends_config: "my_hdldepends_config_0"
vivado_executors:
  my_vivado_executors_key_0:
    executable: "my_executable_0"
    setup:
      - "my_setup_item_0"
      - "my_setup_item_1"
    shell:
      invoke: "my_invoke_0"
      heredoc: true
      mount_repo_root: true
      options:
        - "my_options_item_0"
        - "my_options_item_1"
  my_vivado_executors_key_1:
    executable: "my_executable_1"
    setup:
      - "my_setup_item_2"
      - "my_setup_item_3"
    shell:
      invoke: "my_invoke_1"
      heredoc: false
      mount_repo_root: false
      options:
        - "my_options_item_2"
        - "my_options_item_3"
constraints:
  - file: "my_file_0"
    fileset: "my_fileset_0"
    execution: "my_execution_0"
    properties:
      - "my_properties_item_0"
      - "my_properties_item_1"
  - file: "my_file_1"
    fileset: "my_fileset_1"
    execution: "my_execution_1"
    properties:
      - "my_properties_item_2"
      - "my_properties_item_3"
block_designs:
  - file: "my_file_2"
    commands:
      - "my_commands_item_0"
      - "my_commands_item_1"
  - file: "my_file_3"
    commands:
      - "my_commands_item_2"
      - "my_commands_item_3"
synth_options:
  my_synth_options_key_0: "my_synth_options_0"
  my_synth_options_key_1: "my_synth_options_1"
impl_options:
  my_impl_options_key_0: "my_impl_options_0"
  my_impl_options_key_1: "my_impl_options_1"
build_configuration:
  write_hw_platform:
    include_bit: true
environment_setup:
  my_environment_setup_key_0: "my_environment_setup_0"
  my_environment_setup_key_1: "my_environment_setup_1"
hdlproject_config_version: "my_hdlproject_config_version_0"
```
