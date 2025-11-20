# HDL Project Management System

A modular Python application for managing Xilinx Vivado FPGA projects with automatic dependency resolution, parallel builds, and workflow automation.

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Operations](#operations)
- [Advanced Usage](#advanced-usage)

---

## Overview

`hdlproject` is a project management system designed to streamline FPGA development workflows with Xilinx Vivado. It provides:

- **Unified CLI**: Single `hdlproject` command for all operations
- **Interactive Menu**: User-friendly TUI for project management
- **Batch Mode**: Full CLI support for CI/CD integration
- **Dependency Management**: Automatic HDL compile order resolution (utilising hdldepends)
- **Status Tracking**: Real-time progress visualisation
- **Multi-Project Support**: Process multiple projects in parallel

### Why hdlproject?

Traditional Vivado workflows involve:
- Manual project setup and configuration
- Complex TCL script management
- Manual dependency tracking
- Repetitive GUI operations
- Difficult CI/CD integration

**hdlproject solves these problems** by providing a fully automated, reproducible, and scalable workflow.

---

## Features

### Core Capabilities

- **Project Operations**
  - Build projects from source
  - Open projects in Vivado GUI (edit or view mode)
  - Export projects to archives
  - Publish to CI/CD pipeline
  - etc ... scalable for different operations

- **Configuration Management**
  - YAML-based project configuration
  - Configuration inheritance for reuse
  - Environment variable substitution
  - Automatic validation

- **Dependency Resolution**
  - Automatic HDL compile order generation
  - Integration with `hdldepends` tool

- **Status & Monitoring**
  - Live status display with progress tracking
  - Per-project log files
  - Warning and error aggregation
  - Build time tracking

- **Flexibility**
  - Run from anywhere in git repository
  - Interactive and batch modes
  - Customisable per-repository settings

---

## Prerequisites

### Required Software

1. **Python 3.12+**
   ```bash
   python --version  # Should be 3.12 or higher
   ```

2. **Git**
   ```bash
   git --version
   ```

3. **Xilinx Vivado**
   - Default install location at `/tools/Xilinx/Vivado` (or custom configured path)

4. **[hdldepends](https://github.com/pevhall/hdldepends)** (for automatic compile order
   ```bash
   pip install hdldepends
   ```

### System Requirements

- **OS**: Linux (tested on Ubuntu 20.04+)
- **RAM**: 16GB+ recommended for Vivado
- **Disk**: Sufficient space for Vivado projects and builds

---

## Installation

### Python Virtual Environment
1. Create python virtual environment (venv) local to git repository
2. Install `hdldepends` into the venv
3. Install `hdlproject` into the venv
4. Source the `/path/to/venv/bin/activate`

### Verify Installation

```bash
# Check hdlproject command
which hdlproject
# Should output: /path/to/venv/bin/hdlproject

# Check hdldepends command
which hdldepends
# Should output: /path/to/venv/bin/hdldepends

# Test help
hdlproject --help
```

---

## Quick Start

### 1. Repository Setup

First, configure your repository with `hdlproject_global_config.yaml` at the root:

```yaml
"project_dir": "projects",
"compile_order_script_format": "json",
"default_cores_per_project": 2
# global location, if this doesnt exist, will look for "hdldepends_config" inside of the project specific "hdldepends_project_config.yaml"
"hdldepends_config": "/path/to/hdldepends.json" 
```

### 2. Project Configuration

Create a project configuration file at `projects/my_project/hdlproject_project_config.yaml`:

```yaml
project_information:
  project_name: my_project
  top_level_file_name: top_module
  device_info:
    part_name: xc7a100tcsg324-1
    board_name: Arty A7-100
  vivado_version_year: "2023"
  vivado_version_sub: "2"

constraints:
  - file: constraints/timing.xdc
    fileset: constrs_1

synth_options:
  strategy: Flow_PerfOptimized_high

impl_options:
  strategy: Performance_ExplorePostRoutePhysOpt

hdldepends_config: "/path/to/hdldepends.json" # optional, this overrides global location
```

### 3. Interactive Mode (Recommended for First Use)

```bash
# Navigate to repository
cd /path/to/your/repo

# Launch interactive menu
hdlproject

# Follow prompts:
# 1. Select project(s)
# 2. Choose operation (Build, Open, Export, Publish)
# 3. Configure options
# 4. Watch progress
```

### 4. Batch Mode (For Automation)

```bash
# Build a single project
hdlproject build my_project

# Build multiple projects
hdlproject build project1 project2 project3

# Build with options
hdlproject build my_project --cores 4 --clean

# Open project in edit mode
hdlproject open my_project --mode edit

# Export project
hdlproject export my_project --output-dir ./exports
```

---

## Project Structure

### Example Repository Layout

#### Requirements
- `hdlproject_global_config.yaml` must be at top of repository
- `projects/` directory must match relative path from root of git repository with what was defined in `hdlproject_global_config.yaml`
- each project (i.e. `project1`) must have a `hdlproject_project_config.yaml` file.
- All other directory and file locations are completely customisable

```
my_fpga_repo/
├── hdlproject_global_config.json          # Repository configuration
├── hdldepends.json                 # HDL dependency configuration
├── projects/                       # All projects directory
│   ├── project1/
│   │   ├── hdlproject_project_config.yaml  # Project configuration
│   │   ├── .hdlproject-vivado/build/          # Build artefacts (hidden)
│   │   │   ├── project/            # Vivado project files
│   │   │   ├── logs/               # Operation logs
│   │   │   ├── bd/                 # Block designs
│   │   │   └── xci/                # IP cores
│   │   ├── .hdlproject-vivado/open/           # Open/edit artefacts
│   │   └── .hdlproject-vivado/export/         # Export artefacts
│   └── project2/
│       └── hdlproject_project_config.yaml
├── hdl/                            # HDL source files
│   ├── rtl/
│   │   ├── top_module.vhd
│   │   └── ...
│   └── tb/
├── constraints/                    # Constraint files
│   ├── timing.xdc
│   └── pinout.xdc
└── ip/                            # IP definitions
```

### Hidden Directories

Each operation creates its own hidden directory in the project folder:
- `.hdlproject-vivado/build/` - Build operation artefacts
- `.hdlproject-vivado/open/` - Open/edit operation artefacts
- `.hdlproject-vivado/export/` - Export operation artefacts

These directories are gitignored and can be safely deleted.

---

## Configuration

### Repository Configuration (`hdlproject_global_config.yaml`)


**Options:**
- `project_dir`: Path to projects directory (relative to repo root)
- `compile_order_script_format`: Format for compile order files (`json`, `csv`, `txt`)
- `default_cores_per_project`: Default CPU cores for synthesis/implementation

### Project Configuration (`hdlproject_project_config.yaml`)

Each project needs a YAML configuration file:

```yaml
# Basic project information
project_information:
  project_name: my_project
  top_level_file_name: top_module
  
  # Device specification
  device_info:
    part_name: xc7a100tcsg324-1
    board_name: Arty A7-100
    board_part: digilentinc.com:arty-a7-100:part0:1.1
    vivado_version_year: "2023"
    vivado_version_sub: "2"
  
  # Top-level generics (optional)
  top_level_generics:
    CLK_FREQ:
      type: integer
      value: 100000000
    DEBUG_MODE:
      type: boolean
      value: true

# Constraint files
constraints:
  - file: constraints/my_file.tcl
    fileset: constrs_1
    # the exeuction immediate tag means that this tcl script is immediately executed upon processing into the project and is not added to the project
    execution: immediate
  - file: constraints/pinout.xdc
    fileset: constrs_1

# Block designs (optional)
block_designs:
  - file: system_bd
    # Commands are optional but allow for a single base BD to be modified for different project configurations without needing copies with minor changes between files. Ensure that a single project has NO commands so that the BD can be opened and edited still, as commands create a cached copy of the BD and all changes made will not save to a source controlled area. Commands follow the same TCL commands that you would see in the TCL console in the GUI. They are executed immediately upon including the file into the project.
    commands:
      - <insert command 1>
      - <insert command 2>

# Synthesis options
synth_options:
  strategy: Flow_PerfOptimized_high
  flatten_hierarchy: rebuilt
  fsm_extraction: auto

# Implementation options
impl_options:
  strategy: Performance_ExplorePostRoutePhysOpt
  directive: Default
```

### Configuration Inheritance

Projects can inherit from base configurations:

**`projects/base_arty.yaml`:**
```yaml
project_information:
  device_info:
    part_name: xc7a100tcsg324-1
    board_name: Arty A7-100
    vivado_version_year: "2023"
    vivado_version_sub: "2"

synth_options:
  strategy: Flow_PerfOptimized_high

impl_options:
  strategy: Performance_ExplorePostRoutePhysOpt
```

**`projects/my_project/hdlproject_project_config.yaml`:**
```yaml
inherits: ../base_arty.yaml

project_information:
  project_name: my_project
  top_level_file_name: my_top

# Inherits device_info, synth_options, impl_options from base
```

---

## Usage

### Interactive Mode

```bash
hdlproject
```

**Features:**
- Project selection with multi-select
- Operation menu with descriptions
- Interactive option prompts
- Real-time status display
- Error reporting with log locations

### Batch Mode

#### Global Options

```bash
hdlproject [GLOBAL_OPTIONS] <command> [COMMAND_OPTIONS]
```

**Global Options:**
- `--project-dir PATH` - Override project directory
- `--compile-order-format FORMAT` - Override compile order format (`json`, `csv`, `txt`)
- `--debug` - Enable debug output
- `--verbose` - Enable verbose output
- `--silent` - Disable console output (logs still written)

#### Build Command

```bash
hdlproject build PROJECT [PROJECT...] [OPTIONS]
```

**Options:**
- `--cores N` - CPU cores per project (default: 2)
- `--clean` - Clean build directories before building

**Examples:**
```bash
# Build single project
hdlproject build my_project

# Build multiple projects
hdlproject build proj1 proj2 proj3

# Build with 8 cores
hdlproject build my_project --cores 8

# Clean build
hdlproject build my_project --clean

# Build with verbose output
hdlproject --verbose build my_project
```

#### Open Command

```bash
hdlproject open PROJECT [PROJECT...] [OPTIONS]
```

**Options:**
- `--mode {edit|build}` - Open mode (default: edit)
  - `edit`: Create new project from source
  - `build`: Open existing build project
- `--clean` - Clean open directories (edit mode only)

**Examples:**
```bash
# Open in edit mode
hdlproject open my_project

# Open existing build
hdlproject open my_project --mode build

# Open multiple projects
hdlproject open proj1 proj2
```

#### Export Command

```bash
hdlproject export PROJECT [PROJECT...] [OPTIONS]
```

**Options:**
- `--output-dir PATH` - Custom output directory
- `--clean` - Clean export directories

**Examples:**
```bash
# Export project
hdlproject export my_project

# Export to custom directory
hdlproject export my_project --output-dir ./releases

# Export multiple projects
hdlproject export proj1 proj2 proj3
```

#### Publish Command

```bash
hdlproject publish PROJECT [PROJECT...]
```

**What it does:**
1. Updates build token in `.jenkins/build-token.yaml`
2. Commits or amends current commit
3. Pushes to remote repository
4. Triggers CI/CD pipeline

**Examples:**
```bash
# Publish single project
hdlproject publish my_project

# Publish multiple projects
hdlproject publish proj1 proj2
```

---

## Operations

### Build Operation

**Purpose:** Synthesise, implement, and generate bitstream

**Process:**
1. Generate compile order (if `hdldepends` configured)
2. Create Vivado project from configuration
3. Run synthesis
4. Run implementation
5. Generate bitstream

**Outputs:**
- `.hdlproject-vivado/build/project/` - Vivado project files
- `.hdlproject-vivado/build/logs/build.log` - Detailed log
- `.hdlproject-vivado/build/project/<project>.bit` - Bitstream

### Open Operation

**Purpose:** Open project in Vivado GUI for editing or viewing

**Edit Mode:**
1. Generate compile order
2. Create fresh Vivado project
3. Open GUI for editing

**Build Mode:**
1. Open existing build project
2. View results in GUI

**Outputs:**
- `.hdlproject-vivado/open/project/` - Editable project files
- `.hdlproject-vivado/open/logs/open.log` - Operation log

### Export Operation

**Purpose:** Archive project for distribution or backup

**Process:**
1. Create or open project
2. Archive project files
3. Create compressed archive

**Outputs:**
- `.hdlproject-vivado/export/` - Exported archives
- Archive manifest with metadata

### Publish Operation

**Purpose:** Trigger CI/CD build pipeline

**Process:**
1. Check git status
2. Update build token
3. Commit or amend
4. Push to remote

**Requirements:**
- Clean git working directory
- No uncommitted changes
- Valid remote configuration

---

## Advanced Usage

### Multiple Vivado Versions

Projects can specify different Vivado versions:

```yaml
project_information:
  device_info:
    vivado_version_year: "2023"
    vivado_version_sub: "2"
```

### Custom Compile Order

Configure `hdldepends` in repository root:

**`hdldepends.json`:**
```json
{
  "sub": ["./arty_hdmi_test_project/arty_hdldepends.json"],
  "vhdl_files_glob@2008": [
    "./fw/lib/**/*.vhd"
  ],
  "ext_files_glob": [
    "./fw/lib/**/*.xdc"
  ],
  "ignore_libs": ["ieee", "std", "unisim"]
}
```

### CI/CD Integration

- Batch mode and python package structure allows for easy CI/CD integration

### Parallel Operations

```bash
# Build projects in parallel
hdlproject build proj1 proj2
```

---

## Log Files

### Application Log

**Location:** `bin/hdlproject.log`

**Contains:**
- Application initialisation
- Configuration loading
- Handler execution summary
- Overall errors and warnings

### Project Logs

**Location:** `projects/<project>/.hdlproject-vivado/<operation>/logs/<operation>.log`

**Contains:**
- Complete Vivado output
- Synthesis/implementation details
- Timing reports
- Error and warning messages

---