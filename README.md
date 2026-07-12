# HDL Project Management System

A Python CLI for managing Xilinx Vivado FPGA projects with automatic dependency resolution, parallel builds, and workflow automation.

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Features

- **Fast keyboard TUI** — Quick prompt-driven menu (select projects → operation → options), or scriptable batch mode
- **Parallel Builds** — Process multiple projects concurrently
- **Cancellable** — Ctrl+C stops a running build cleanly; no orphaned Vivado processes
- **Dependency Resolution** — Automatic HDL compile order via [hdldepends](https://github.com/pevhall/hdldepends)
- **YAML Configuration** — Inheritance, environment variables, and validation
- **Real-time Status** — Live per-step progress with warning/error aggregation

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.12+ | `python --version` |
| Git | Must run from within a git repository |
| Xilinx Vivado | Default location: `/tools/Xilinx/Vivado` |
| hdldepends | `pip install hdldepends` |

**Platform:** Linux (tested on Ubuntu 20.04+)

## Installation

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install hdldepends
pip install hdlproject  # or pip install -e . for development
```

Verify installation:
```bash
hdlproject --help
```

## Setup

### 1. Global Configuration

Create `hdlproject_global_config.yaml` at repository root:

```yaml
project_dir: "projects"
hdldepends_config: "hdldepends.json"
compile_order_format: "json"
default_cores: 2

tools:
  vivado:
    "2020.1":
      setup:
        - "source /tools/Xilinx/Vivado/2020.1/settings64.sh"
      executable: "vivado"
```

### 2. Project Configuration

Create `hdlproject_project_config.yaml` in each project directory (e.g., `projects/my_project/`).

See [YAML Configuration Guide](docs/yaml-configuration-guide.md) for full schema and options.

### Repository Structure

```
my_repo/
├── hdlproject_global_config.yaml   # Required: repository settings
├── hdldepends.json                 # HDL dependency configuration
├── projects/
│   ├── project1/
│   │   └── hdlproject_project_config.yaml
│   └── project2/
│       └── hdlproject_project_config.yaml
├── hdl/                            # HDL sources (location flexible)
└── constraints/                    # Constraint files (location flexible)
```

## Usage

### Interactive Mode

```bash
hdlproject
```

Launches a fast keyboard-driven menu:

1. Select one or more projects — **space** to toggle, **enter** to confirm.
2. Choose an operation (build / open / export / publish) with the arrow keys.
3. Answer the operation prompts (e.g. clean? cores?).

A live status tree then renders per-step progress during the run. Press **Ctrl+C**
to cancel cleanly; build failures are reported before returning to the menu.

### Batch Mode

```bash
hdlproject <command> <projects...> [options]
```

#### Commands

| Command | Description |
|---------|-------------|
| `build` | Synthesise, implement, and generate bitstream |
| `open` | Open project in Vivado GUI |
| `export` | Archive project for distribution |
| `publish` | Trigger CI/CD pipeline |

#### Examples

```bash
# Build single project
hdlproject build my_project

# Build multiple projects with 8 cores each
hdlproject build proj1 proj2 --cores 8 --clean

# Open project for editing
hdlproject open my_project --mode edit

# Open existing build result
hdlproject open my_project --mode build

# Export project
hdlproject export my_project --output-dir ./releases

# Publish to CI/CD
hdlproject publish my_project
```

#### Global Options

| Option | Description |
|--------|-------------|
| `--project-dir PATH` | Override project directory |
| `--compile-order-format` | Output format: `json`, `csv`, `txt` |
| `--debug` | Enable debug output |
| `--verbose` | Enable verbose output |
| `--silent` | Suppress console output (logs still written) |

## Output Locations

Each operation creates artefacts in hidden directories within the project folder:

| Operation | Directory | Key Outputs |
|-----------|-----------|-------------|
| build | `.hdlproject-vivado/build/` | `project/<name>.bit`, `logs/build.log` |
| open | `.hdlproject-vivado/open/` | `project/`, `logs/open.log` |
| export | `.hdlproject-vivado/export/` | Archive files, manifest |

**Application log:** `bin/hdlproject.log`

These directories are safe to delete and should be gitignored.

## Documentation

- [YAML Configuration Guide](docs/yaml-configuration-guide.md) — Full configuration schema reference
- [Architecture](docs/architecture.md) — How the execution core, progress sinks, and front-ends fit together

## Development

```bash
pip install -e ".[dev]"   # editable install with dev tools
pre-commit install        # regenerates docs/yaml-configuration-guide.md on model changes

pytest                    # run the test suite
ruff check src/           # lint
mypy src/hdlproject       # type-check
```

The configuration schema is frozen by a test (`test/unit/test_schema_freeze.py`):
intentional, additive schema changes require regenerating the baseline. See that
test's docstring.

## License

MIT