# utils/vivado_output_parser.py
"""Vivado output parsing"""

import re
from typing import Optional, NamedTuple, Any
from enum import Enum, auto
from dataclasses import dataclass

from hdlproject.utils.logging_manager  import get_logger

logger = get_logger(__name__)


class MessageType(Enum):
    """Types of messages that can be detected"""
    ERROR = auto()
    CRITICAL_WARNING = auto()
    WARNING = auto()
    INFO = auto()
    STEP_UPDATE = auto()


class ParsedMessage(NamedTuple):
    """Result of parsing a line"""
    type: MessageType
    message: str
    step_name: Optional[str] = None
    is_failure: bool = False


@dataclass
class StepPattern:
    """Maps Vivado output patterns to operation steps"""
    step_name: str
    patterns: list[str]
    is_error: bool = False


class VivadoOutputParser:
    """Centralised parser for Vivado output"""
    
    # Single source of truth for error patterns
    ERROR_PATTERNS = [
        r'^error[:\s]',
        r'^\[error\]',
        r'{error}',
        r'ERROR:',
        r'\[ERROR\]',
        r'{ERROR}'
    ]
    
    # Single source of truth for warning patterns
    CRITICAL_WARNING_PATTERNS = [
        r'critical warning[:\s]',
        r'\[critical warning\]',
        r'{critical warning}',
        r'CRITICAL WARNING:',
    ]
    
    WARNING_PATTERNS = [
        r'^warning[:\s]',
        r'^\[warning\]',
        r'{warning}',
        r'WARNING:',
    ]
    
    # False positive patterns to exclude
    FALSE_POSITIVE_PATTERNS = [
        'error_msg',
        'no error',
        'error_count',
        'warning_msg',
        'no warning'
    ]
    
    def __init__(self, step_patterns: Optional[list[StepPattern]] = None):
        """
        Initialise parser with optional step patterns for operation tracking.
        
        Args:
            step_patterns: list of StepPattern objects for detecting operation steps
        """
        self.step_patterns = step_patterns or []
        
        # Compile regex patterns for efficiency
        self._error_regex = [re.compile(p, re.IGNORECASE) for p in self.ERROR_PATTERNS]
        self._critical_warning_regex = [re.compile(p, re.IGNORECASE) for p in self.CRITICAL_WARNING_PATTERNS]
        self._warning_regex = [re.compile(p, re.IGNORECASE) for p in self.WARNING_PATTERNS]
        
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
        
        # Check for errors
        if self._is_error(line_stripped):
            return ParsedMessage(MessageType.ERROR, line_stripped, is_failure=True)
        
        # Check for critical warnings
        if self._is_critical_warning(line_stripped):
            return ParsedMessage(MessageType.CRITICAL_WARNING, line_stripped)
        
        # Check for regular warnings
        if self._is_warning(line_stripped):
            return ParsedMessage(MessageType.WARNING, line_stripped)
        
        # Check for step updates
        step_result = self._check_step_patterns(line_stripped)
        if step_result:
            return step_result
        
        # Default to info
        return ParsedMessage(MessageType.INFO, line_stripped)
    
    def _is_error(self, line: str) -> bool:
        """Check if line contains an error"""
        return any(regex.search(line) for regex in self._error_regex)
    
    def _is_critical_warning(self, line: str) -> bool:
        """Check if line contains a critical warning"""
        return any(regex.search(line) for regex in self._critical_warning_regex)
    
    def _is_warning(self, line: str) -> bool:
        """Check if line contains a regular warning"""
        return any(regex.search(line) for regex in self._warning_regex)
    
    def _check_step_patterns(self, line: str) -> Optional[ParsedMessage]:
        """Check if line matches any step patterns"""
        for step, compiled_patterns in self._compiled_step_patterns:
            if any(pattern.search(line) for pattern in compiled_patterns):
                return ParsedMessage(
                    MessageType.STEP_UPDATE,
                    line,
                    step_name=step.step_name,
                    is_failure=step.is_error
                )
        return None
    
    @classmethod
    def create_from_definition(cls, step_patterns: list[dict[str, Any]]) -> 'VivadoOutputParser':
        """
        Create parser from handler definition step patterns.
        
        Args:
            step_patterns: list of step pattern dictionaries from handler definition
            
        Returns:
            Configured VivadoOutputParser instance
        """
        patterns = []
        for pattern_def in step_patterns:
            patterns.append(StepPattern(
                step_name=pattern_def['step_name'],
                patterns=pattern_def['patterns'],
                is_error=pattern_def.get('is_error', False)
            ))
        
        return cls(patterns)