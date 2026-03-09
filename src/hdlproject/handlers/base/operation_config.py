# handlers/base/operation_config.py
"""Operation configuration - declarative handler metadata.

This module defines the OperationConfig dataclass that handlers use to
declare their metadata, TCL modes, and step patterns.
"""

from dataclasses import dataclass

from hdlproject.utils.vivado_output_parser import StepPattern


@dataclass
class OperationConfig:
    """Declarative operation metadata.

    Each handler defines this as a class attribute (CONFIG).

    Attributes:
        name: Operation name (build, open, export, etc.)
        tcl_mode: TCL script mode to use
        step_patterns: Patterns for parsing Vivado output
        operation_steps: Steps to display in status
        supports_gui: Whether this operation opens GUI
        supports_parallel: Whether this operation supports parallel execution
    """

    name: str
    tcl_mode: str
    step_patterns: list[StepPattern]
    operation_steps: list[str]
    supports_gui: bool = False
    supports_parallel: bool = True
