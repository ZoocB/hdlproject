"""Handlers module.

This module provides handlers for various operations (build, export, etc.)
"""

from hdlproject.handlers.registry import (
    HandlerInfo,
    register_handler,
    get_handler,
    get_all_handlers,
    get_menu_handlers,
    load_all_handlers,
)

__all__ = [
    "HandlerInfo",
    "register_handler",
    "get_handler",
    "get_all_handlers",
    "get_menu_handlers",
    "load_all_handlers",
]
