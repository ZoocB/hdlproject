# utils/__init__.py
"""Utility functions and classes"""

from hdlproject.utils.logging_manager import (
    get_logger,
    get_project_logger,
    setup_application_log,
    setup_project_log,
    set_verbosity,
    is_silent,
    should_show_status_display,
    cleanup,
    LogLevel
)
from hdlproject.utils.status_display import (
    LiveStatusDisplay, 
    DisplayMode, 
    MessageLevel
)
from hdlproject.utils.vivado_output_parser import (
    VivadoOutputParser, 
    MessageType, 
    StepPattern
)

from hdlproject.utils.resources import *

__all__ = [
    # Logging
    'get_logger',
    'get_project_logger',
    'setup_application_log',
    'setup_project_log',
    'set_verbosity',
    'is_silent',
    'should_show_status_display',
    'cleanup',
    'LogLevel',
    
    # Status display
    'LiveStatusDisplay',
    'DisplayMode',
    'MessageLevel',
    
    # Output parsing
    'VivadoOutputParser',
    'MessageType',
    'StepPattern'
]