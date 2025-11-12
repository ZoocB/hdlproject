# handlers/base/operation_config.py
"""Operation configuration - declarative handler metadata"""

from dataclasses import dataclass

from hdlproject.utils.vivado_output_parser import StepPattern


@dataclass
class OperationConfig:
    """
    Declarative operation metadata.
    Each handler defines this as a class attribute.
    """
    name: str                           # Operation name (build, open, export, etc.)
    tcl_mode: str                       # TCL script mode to use
    step_patterns: list[StepPattern]    # Patterns for parsing Vivado output
    operation_steps: list[str]          # Steps to display in status
    supports_gui: bool = False          # Whether this operation opens GUI