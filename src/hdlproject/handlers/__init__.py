# handlers/__init__.py
"""Handler package - handlers self-register when imported"""

# Re-export registry functions for convenience
from hdlproject.handlers.registry import (
    get_handler,
    get_all_handlers,
    get_menu_handlers,
    load_all_handlers
)

__all__ = [
    'get_handler',
    'get_all_handlers', 
    'get_menu_handlers',
    'load_all_handlers'
]