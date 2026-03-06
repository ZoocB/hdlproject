"""Project-wide constants and configuration filenames."""

# Configuration filenames
PROJECT_CONFIG_FILENAME = "hdlproject_project_config.yaml"
GLOBAL_CONFIG_FILENAME = "hdlproject_global_config.yaml"

# Directory names
HDLPROJECT_DIR_BASE = "hdlproject"
HDLPROJECT_VHDL2008_DIR = f"{HDLPROJECT_DIR_BASE}_vhdl2008"
HDLPROJECT_VERILOG_DIR = f"{HDLPROJECT_DIR_BASE}_verilog"

# Known operations
KNOWN_BUILD_OPERATIONS = ["build", "open", "export", "publish"]

# Configuration
DEFAULT_MAX_PARALLEL_BUILDS = 4
DEFAULT_CORES_PER_PROJECT = 1

# Vivado tool names
VIVADO_TOOL_NAME = "vivado"
XSIM_TOOL_NAME = "xsim"
