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
  - [BuildVariable](#buildvariable)
  - [GeneratedSource](#generatedsource)
  - [BuildConfiguration](#buildconfiguration)
  - [Constraint](#constraint)
  - [DeviceInfo](#deviceinfo)
  - [ShellConfig](#shellconfig)
  - [ToolExecutor](#toolexecutor)
  - [GlobalConfiguration](#globalconfiguration)
  - [HooksConfig](#hooksconfig)
  - [ProjectInformation](#projectinformation)
  - [ProjectConfiguration](#projectconfiguration)
  - [VivadoVersion](#vivadoversion)
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

### BuildVariable

A build-time variable resolved before synthesis.

Use `value` for static data or `command` for dynamically computed data.
Exactly one of `value` or `command` must be set.

Example:
```yaml
build_variables:
  version_major:
    value: 1
  git_hash:
    command: "git rev-parse --short HEAD"
  build_date:
    command: "date +%y%m%d"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `value` | str | int | float | No | `null` | Static value for this variable. |
| `command` | str | No | `null` | Shell command to execute. stdout is captured and stripped as the value. |

### GeneratedSource

A Jinja2 template that is rendered at build time and added to the project.

The template has access to the full resolved project configuration
and resolved build variables. Reference values explicitly:
- ``{{ build_variables.version_major }}``
- ``{{ project_information.project_name }}``
- ``{{ project_information.device_info.board_name }}``

Example:
```yaml
generated_sources:
  - template: "hdl/build_info_pkg.vhd.j2"
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `template` | str | Yes | `—` | Path to Jinja2 template file, relative to the YAML config file. |

### BuildConfiguration

Build-time configuration for synthesis and implementation.

These are persistent options stored in the config, distinct from
CLI runtime options like --cores or --clean.

Example:
```yaml
build_configuration:
  artefact_name: "{{ project_information.project_name | upper }}_v{{ build_variables.version_major }}"
  build_variables:
    version_major:
      value: 1
    version_minor:
      value: 0
    git_hash:
      command: "git rev-parse --short HEAD"
  generated_sources:
    - template: "hdl/build_info_pkg.vhd.j2"
  write_hw_platform:
    include_bit: true
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `artefact_name` | str | No | `null` | Jinja2 template string for the build artefact name. Rendered with the full resolved config and build variables as context.  |
| `build_variables` | dict[str, [BuildVariable](#buildvariable)] | No | `{}` | Build-time variables resolved before synthesis. Keys are variable names. |
| `generated_sources` | list[[GeneratedSource](#generatedsource)] | No | `[]` | Jinja2 templates rendered at build time and added as project sources. |
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

### ToolExecutor

Configuration for executing a specific tool version.

Defines how to execute a tool (e.g., Vivado) and related utilities
(like hdldepends) for a specific version. Supports both local
installations and containerised environments.

The execution flow is: [shell] → [setup] → [injected commands] → [executable]

Example:
```yaml
tools:
  vivado:
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

tools:
  vivado:
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
| `tools` | dict[str, dict[str, [ToolExecutor](#toolexecutor)]] | No | `{}` | Tool execution configs keyed by tool name then version. e.g., tools.vivado.'2020.1'. Overridable per-project. |
| `default_cores` | int | No | `2` | Default CPU cores per project for synthesis/implementation. |
| `max_parallel_builds` | int | No | `null` | Maximum parallel builds. If None, calculated from system resources. |
| `compile_order_format` | str | No | `'json'` | Output format for compile order files ('json' or 'tcl'). |

### HooksConfig

TCL hook points for injecting custom commands at lifecycle stages.

Each hook is a list of TCL commands executed at that point in the workflow.
Hooks run inside the Vivado TCL interpreter and have access to the full
Vivado command set plus all project context variables.

Example:
```yaml
hooks:
  post_project_create:
    - "set_property IP_REPO_PATHS /path/to/custom_ips [current_project]"
    - "update_ip_catalog"
  pre_synthesis:
    - 'source "$env(REPO_ROOT)/scripts/pre_synth_checks.tcl"'
  post_implementation:
    - "report_utilization -file utilization.rpt"
  post_bitstream:
    - 'source "$env(REPO_ROOT)/scripts/post_build.tcl"'
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `post_project_create` | list[str] | No | `[]` | Run after project creation and standard property setup. |
| `post_project_setup` | list[str] | No | `[]` | Run after all project components (sources, constraints, IPs, BDs) are loaded. |
| `pre_build` | list[str] | No | `[]` | Run before the build flow starts (before synthesis). |
| `pre_synthesis` | list[str] | No | `[]` | Run immediately before synthesis launch. |
| `post_synthesis` | list[str] | No | `[]` | Run after synthesis completes successfully. |
| `pre_implementation` | list[str] | No | `[]` | Run immediately before implementation launch. |
| `post_implementation` | list[str] | No | `[]` | Run after implementation completes successfully. |
| `post_bitstream` | list[str] | No | `[]` | Run after bitstream generation and artefact packaging. |

### ProjectInformation

Core project identification and settings.

Example:
```yaml
project_information:
  project_name: my_project
  top_level_file_name: top_level
  tool: vivado
  tool_version: "2020.1"
  device_info:
    part_name: xc7z020clg400-1
    board_name: Arty_Z7_20
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project_name` | str | Yes | `—` | Tool project name. Used for project file and output naming. |
| `top_level_file_name` | str | Yes | `—` | Top-level HDL module filename (without path or extension). |
| `device_info` | [DeviceInfo](#deviceinfo) | Yes | `—` | FPGA device and board configuration. |
| `tool` | str | No | `'vivado'` | EDA tool to use for this project (e.g., 'vivado'). |
| `tool_version` | str | Yes | `—` | Tool version string (e.g., '2020.1'). |

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
| `tools` | dict[str, dict[str, [ToolExecutor](#toolexecutor)]] | No | `null` | Project-specific tool executors. Overrides global settings. Keyed by tool name then version. |
| `constraints` | list[[Constraint](#constraint)] | No | `[]` | Constraint files to include. |
| `block_designs` | list[[BlockDesign](#blockdesign)] | No | `[]` | Block designs to include. |
| `synth_options` | dict[str, str] | No | `{}` | Vivado synthesis properties (STEPS.SYNTH_DESIGN.ARGS.*). |
| `impl_options` | dict[str, str] | No | `{}` | Vivado implementation properties (STEPS.*.ARGS.*). |
| `build_configuration` | [BuildConfiguration](#buildconfiguration) | No | `BuildConfiguration(artefact_name=None, build_variables={}, generated_sources=[], write_hw_platform=WriteHwPlatformOptions(include_bit=False))` | Build-time configuration options. |
| `hooks` | [HooksConfig](#hooksconfig) | No | `HooksConfig(post_project_create=[], post_project_setup=[], pre_build=[], pre_synthesis=[], post_synthesis=[], pre_implementation=[], post_implementation=[], post_bitstream=[])` | TCL hook points for injecting custom commands at workflow lifecycle stages. |
| `environment_setup` | dict[str, str] | No | `null` | Pre-processing scripts. Keys: executor, Values: script path. Output KEY=VALUE lines added to env. |
| `hdlproject_config_version` | str | No | `'4.0.0'` | Configuration schema version. |

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

## Complete Examples

Auto-generated examples showing all fields with dummy values.

### Global Configuration Example

```yaml
project_dir: "my_project_dir_0"
hdldepends_config: "my_hdldepends_config_0"
tools:
  my_tools_key_0: "my_tools_0"
  my_tools_key_1: "my_tools_1"
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
  tool: "my_tool_0"
  tool_version: "my_tool_version_0"
hdldepends_config: "my_hdldepends_config_0"
tools:
  my_tools_key_0: "my_tools_0"
  my_tools_key_1: "my_tools_1"
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
  artefact_name: "my_artefact_name_0"
  build_variables:
    my_build_variables_key_0:
      value: "my_value_0"
      command: "my_command_0"
    my_build_variables_key_1:
      value: "my_value_1"
      command: "my_command_1"
  generated_sources:
    - template: "my_template_0"
    - template: "my_template_1"
  write_hw_platform:
    include_bit: true
hooks:
  post_project_create:
    - "my_post_project_create_item_0"
    - "my_post_project_create_item_1"
  post_project_setup:
    - "my_post_project_setup_item_0"
    - "my_post_project_setup_item_1"
  pre_build:
    - "my_pre_build_item_0"
    - "my_pre_build_item_1"
  pre_synthesis:
    - "my_pre_synthesis_item_0"
    - "my_pre_synthesis_item_1"
  post_synthesis:
    - "my_post_synthesis_item_0"
    - "my_post_synthesis_item_1"
  pre_implementation:
    - "my_pre_implementation_item_0"
    - "my_pre_implementation_item_1"
  post_implementation:
    - "my_post_implementation_item_0"
    - "my_post_implementation_item_1"
  post_bitstream:
    - "my_post_bitstream_item_0"
    - "my_post_bitstream_item_1"
environment_setup:
  my_environment_setup_key_0: "my_environment_setup_0"
  my_environment_setup_key_1: "my_environment_setup_1"
hdlproject_config_version: "my_hdlproject_config_version_0"
```
