# utils/vivado_output_parser.py
"""Vivado output parsing with step result handling"""

import re
from typing import Optional, NamedTuple
from enum import Enum, auto
from dataclasses import dataclass

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class MessageType(Enum):
    """Types of messages that can be detected"""

    ERROR = auto()
    CRITICAL_WARNING = auto()
    WARNING = auto()
    INFO = auto()
    STEP_UPDATE = auto()
    PROJECT_CONTEXT = auto()
    BUILD_ARTEFACTS = auto()
    TIMING_RESULT = auto()


class StepResultType(Enum):
    """Result type for step completion"""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ParsedMessage(NamedTuple):
    """Result of parsing a line"""

    type: MessageType
    message: str
    step_name: Optional[str] = None
    is_failure: bool = False
    step_result: Optional[StepResultType] = None
    warning_count: int = 0
    critical_warning_count: int = 0
    error_count: int = 0
    project_context_name: Optional[str] = None
    build_artefacts_path: Optional[str] = None
    is_step_start: bool = False
    is_tcl_step: bool = False
    # Timing result fields
    timing_passed: Optional[bool] = None
    timing_report_path: Optional[str] = None


@dataclass
class StepPattern:
    """Maps Vivado output patterns to operation steps"""

    step_name: str
    patterns: list[str]
    is_start: bool = False
    is_tcl_step: bool = False
    is_failure_pattern: bool = False  # True if this pattern indicates step failure

    @classmethod
    def tcl(cls, step_name: str, proc_name: str) -> "StepPattern":
        """
        Create a StepPattern for TCL HDLPROJECT_STEP_* markers.

        Auto-expands to match SUCCESS, WARNING, and ERROR variants.
        Only HDLPROJECT_STEP_ERROR will cause a failure.

        During hdlproject specific TCL steps, regular Vivado errors are ignroed, only
        HDLPROJECT_STEP_ERROR causes the step to be marked as failed.

        Args:
            step_name: User-facing step name (e.g., "Processing IP Cores")
            proc_name: TCL procedure name (e.g., "handle_xcis::process_xcis")
        """
        return cls(
            step_name=step_name,
            patterns=[
                rf"\[HDLPROJECT_STEP_SUCCESS\] {proc_name}",
                rf"\[HDLPROJECT_STEP_WARNING\] {proc_name}",
                rf"\[HDLPROJECT_STEP_ERROR\] {proc_name}",
            ],
            is_tcl_step=True,
        )

    @classmethod
    def start(cls, step_name: str, pattern: str) -> "StepPattern":
        """
        Create a StepPattern for step start detection.

        During Vivado steps (start/complete), regular Vivado errors,
        warnings, and critical warnings ARE tracked.

        Args:
            step_name: User-facing step name
            pattern: Regex pattern indicating step is starting
        """
        return cls(
            step_name=step_name, patterns=[pattern], is_start=True, is_tcl_step=False
        )

    @classmethod
    def complete(cls, step_name: str, pattern: str) -> "StepPattern":
        """
        Create a StepPattern for step completion detection.

        Args:
            step_name: User-facing step name
            pattern: Regex pattern indicating step completed
        """
        return cls(
            step_name=step_name, patterns=[pattern], is_start=False, is_tcl_step=False
        )

    @classmethod
    def failed(cls, step_name: str, pattern: str) -> "StepPattern":
        """
        Create a StepPattern for step failure detection.

        Args:
            step_name: User-facing step name
            pattern: Regex pattern indicating step failed
        """
        return cls(
            step_name=step_name,
            patterns=[pattern],
            is_start=False,
            is_tcl_step=False,
            is_failure_pattern=True,
        )


class VivadoOutputParser:
    """Centralised parser for Vivado output with step result detection"""

    # Single source of truth for error patterns
    ERROR_PATTERNS = [
        r"^error[:\s]",
        r"^\[error\]",
        r"{error}",
        r"ERROR:",
        r"\[ERROR\]",
        r"{ERROR}",
    ]

    # Single source of truth for warning patterns
    CRITICAL_WARNING_PATTERNS = [
        r"critical warning[:\s]",
        r"\[critical warning\]",
        r"{critical warning}",
        r"CRITICAL WARNING:",
    ]

    WARNING_PATTERNS = [
        r"^warning[:\s]",
        r"^\[warning\]",
        r"{warning}",
        r"WARNING:",
    ]

    # False positive patterns to exclude
    FALSE_POSITIVE_PATTERNS = [
        "error_msg",
        "no error",
        "error_count",
        "warning_msg",
        "no warning",
    ]

    def __init__(self, step_patterns: Optional[list[StepPattern]] = None):
        """
        Initialise parser with step patterns for operation tracking.

        Args:
            step_patterns: list of StepPattern objects for detecting operation steps
        """
        self.step_patterns = step_patterns or []

        # Compile regex patterns for efficiency
        self._error_regex = [re.compile(p, re.IGNORECASE) for p in self.ERROR_PATTERNS]
        self._critical_warning_regex = [
            re.compile(p, re.IGNORECASE) for p in self.CRITICAL_WARNING_PATTERNS
        ]
        self._warning_regex = [
            re.compile(p, re.IGNORECASE) for p in self.WARNING_PATTERNS
        ]

        # Pattern to extract counts from step results: [W:3 E:1] or [W:3] or [E:1]
        self._count_pattern = re.compile(r"\[(?:W:(\d+))?\s*(?:E:(\d+))?\]")

        # Compile step patterns
        self._compiled_step_patterns = []
        for step in self.step_patterns:
            compiled_patterns = [re.compile(p, re.IGNORECASE) for p in step.patterns]
            self._compiled_step_patterns.append((step, compiled_patterns))

    def parse_line(self, line: str) -> ParsedMessage:
        """
        Parse a single line of Vivado output.

        Args:
            line: Raw output line from Vivado

        Returns:
            ParsedMessage with type, content, and optional step information
        """
        line_stripped = line.strip()

        if not line_stripped:
            return ParsedMessage(MessageType.INFO, line_stripped)

        line_lower = line_stripped.lower()

        # Check for false positives first
        if any(fp in line_lower for fp in self.FALSE_POSITIVE_PATTERNS):
            return ParsedMessage(MessageType.INFO, line_stripped)

        # Check for project context marker
        if "[HDLPROJECT_PROJECT_CONTEXT]" in line_stripped:
            name = self._extract_project_context_name(line_stripped)
            return ParsedMessage(
                MessageType.PROJECT_CONTEXT, line_stripped, project_context_name=name
            )

        # Check for build artefacts marker
        if "[HDLPROJECT_BUILD_ARTEFACTS]" in line_stripped:
            path = self._extract_build_artefacts_path(line_stripped)
            return ParsedMessage(
                MessageType.BUILD_ARTEFACTS, line_stripped, build_artefacts_path=path
            )

        # Check for timing result marker
        if "[HDLPROJECT_TIMING_RESULT]" in line_stripped:
            timing_passed, report_path = self._extract_timing_result(line_stripped)
            return ParsedMessage(
                MessageType.TIMING_RESULT,
                line_stripped,
                timing_passed=timing_passed,
                timing_report_path=report_path,
            )

        # Check for step updates via pattern matching FIRST
        # This ensures HDLPROJECT_STEP_* patterns are handled as step updates
        step_result = self._check_step_patterns(line_stripped)
        if step_result:
            return step_result

        # Check for errors (regular Vivado errors)
        if self._is_error(line_stripped):
            return ParsedMessage(MessageType.ERROR, line_stripped)

        # Check for critical warnings
        if self._is_critical_warning(line_stripped):
            return ParsedMessage(MessageType.CRITICAL_WARNING, line_stripped)

        # Check for regular warnings
        if self._is_warning(line_stripped):
            return ParsedMessage(MessageType.WARNING, line_stripped)

        # Default to info
        return ParsedMessage(MessageType.INFO, line_stripped)

    def _extract_project_context_name(self, line: str) -> Optional[str]:
        """Extract project context name from line"""
        # Format: [HDLPROJECT_PROJECT_CONTEXT] name=MY_BUILD_NAME
        match = re.search(r"\[HDLPROJECT_PROJECT_CONTEXT\]\s*name=(.+)$", line)
        if match:
            return match.group(1).strip()
        return None

    def _extract_build_artefacts_path(self, line: str) -> Optional[str]:
        """Extract build artefacts path from line"""
        # Format: [HDLPROJECT_BUILD_ARTEFACTS] /path/to/artefacts
        match = re.search(r"\[HDLPROJECT_BUILD_ARTEFACTS\]\s*(.+)$", line)
        if match:
            return match.group(1).strip()
        return None

    def _extract_timing_result(self, line: str) -> tuple[Optional[bool], Optional[str]]:
        """Extract timing result from line

        Format: [HDLPROJECT_TIMING_RESULT] status=PASSED report=/path/to/report.rpt
        or:     [HDLPROJECT_TIMING_RESULT] status=FAILED report=/path/to/report.rpt

        Returns:
            tuple of (timing_passed, report_path)
        """
        timing_passed = None
        report_path = None

        # Extract status
        status_match = re.search(r"status=(\w+)", line)
        if status_match:
            status = status_match.group(1).upper()
            timing_passed = status == "PASSED"

        # Extract report path
        report_match = re.search(r"report=(.+?)(?:\s|$)", line)
        if report_match:
            report_path = report_match.group(1).strip()

        return timing_passed, report_path

    def _is_error(self, line: str) -> bool:
        """Check if line contains an error"""
        return any(regex.search(line) for regex in self._error_regex)

    def _is_critical_warning(self, line: str) -> bool:
        """Check if line contains a critical warning"""
        return any(regex.search(line) for regex in self._critical_warning_regex)

    def _is_warning(self, line: str) -> bool:
        """Check if line contains a regular warning"""
        # Exclude critical warnings from regular warning detection
        if self._is_critical_warning(line):
            return False
        return any(regex.search(line) for regex in self._warning_regex)

    def _check_step_patterns(self, line: str) -> Optional[ParsedMessage]:
        """
        Check if line matches any step patterns.

        Handles HDLPROJECT_STEP_* patterns for TCL steps and start/complete/failed
        patterns for Vivado build phases.
        """
        for step, compiled_patterns in self._compiled_step_patterns:
            if any(pattern.search(line) for pattern in compiled_patterns):
                # Determine result type and counts based on line content
                step_result = None
                warning_count = 0
                critical_warning_count = 0
                error_count = 0
                is_failure = False
                is_step_start = step.is_start
                is_tcl_step = step.is_tcl_step

                # Check for HDLPROJECT_STEP_* prefixes to determine result type
                if "[HDLPROJECT_STEP_SUCCESS]" in line:
                    step_result = StepResultType.SUCCESS
                elif "[HDLPROJECT_STEP_WARNING]" in line:
                    step_result = StepResultType.WARNING
                    # Extract counts from TCL step output
                    count_match = self._count_pattern.search(line)
                    if count_match:
                        if count_match.group(1):
                            warning_count = int(count_match.group(1))
                        if count_match.group(2):
                            error_count = int(count_match.group(2))
                elif "[HDLPROJECT_STEP_ERROR]" in line:
                    step_result = StepResultType.ERROR
                    is_failure = True  # Only HDLPROJECT_STEP_ERROR causes failure
                    # Extract counts
                    count_match = self._count_pattern.search(line)
                    if count_match:
                        if count_match.group(1):
                            warning_count = int(count_match.group(1))
                        if count_match.group(2):
                            error_count = int(count_match.group(2))
                elif step.is_failure_pattern:
                    # Vivado step failure pattern (e.g., "synth_design failed")
                    step_result = StepResultType.ERROR
                    is_failure = True
                elif not is_step_start:
                    # Completion pattern without HDLPROJECT marker = implicit success
                    step_result = StepResultType.SUCCESS

                return ParsedMessage(
                    MessageType.STEP_UPDATE,
                    line,
                    step_name=step.step_name,
                    is_failure=is_failure,
                    step_result=step_result,
                    warning_count=warning_count,
                    critical_warning_count=critical_warning_count,
                    error_count=error_count,
                    is_step_start=is_step_start,
                    is_tcl_step=is_tcl_step,
                )
        return None
