# handlers/registry.py
"""Simplified handler registry"""

from typing import Any, Type, Optional
from dataclasses import dataclass, field

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


@dataclass
class HandlerInfo:
    """Handler information"""

    name: str
    handler_class: Type
    options_class: Type
    description: str
    menu_name: str
    cli_arguments: list[dict[str, Any]]
    supports_multiple: bool = True
    artefact_definitions: list = field(default_factory=list)

    def create_handler(self, environment: dict[str, Any], interactive: bool = False):
        """Create handler instance with environment"""
        return self.handler_class(environment=environment, interactive=interactive)

    def create_options(self, **kwargs):
        """Create options instance with only valid parameters"""
        import inspect

        sig = inspect.signature(self.options_class)
        valid_params = set(sig.parameters.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        return self.options_class(**filtered_kwargs)


class HandlerRegistry:
    """Simple registry for handlers"""

    def __init__(self):
        self._handlers: dict[str, HandlerInfo] = {}

    def register(self, info: HandlerInfo) -> None:
        """Register a handler"""
        if info.name in self._handlers:
            logger.warning(f"Handler '{info.name}' already registered, overwriting")

        self._handlers[info.name] = info
        logger.debug(f"Registered handler: {info.name}")

    def get(self, name: str) -> Optional[HandlerInfo]:
        """Get handler info by name"""
        return self._handlers.get(name)

    def get_all(self) -> dict[str, HandlerInfo]:
        """Get all registered handlers"""
        return self._handlers.copy()

    def get_menu_handlers(
        self, for_multiple_projects: bool = False
    ) -> list[tuple[str, HandlerInfo]]:
        """Get handlers suitable for menu display"""
        handlers = []

        for name, info in self._handlers.items():
            if for_multiple_projects and not info.supports_multiple:
                continue
            handlers.append((name, info))

        return sorted(handlers, key=lambda x: x[1].menu_name)


# Global registry instance
_registry = HandlerRegistry()


def register_handler(info: HandlerInfo) -> None:
    """Register a handler in the global registry"""
    _registry.register(info)


def get_handler(name: str) -> Optional[HandlerInfo]:
    """Get handler from global registry"""
    return _registry.get(name)


def get_all_handlers() -> dict[str, HandlerInfo]:
    """Get all handlers from global registry"""
    return _registry.get_all()


def get_menu_handlers(
    for_multiple_projects: bool = False,
) -> list[tuple[str, HandlerInfo]]:
    """Get menu handlers from global registry"""
    return _registry.get_menu_handlers(for_multiple_projects)


def load_all_handlers():
    """Explicitly load all handler modules to trigger registration"""
    # Import all handler modules to trigger their registration
    from hdlproject.handlers import build
    from hdlproject.handlers import open_project
    from hdlproject.handlers import export
    from hdlproject.handlers import publish

    logger.debug(f"Loaded {len(_registry.get_all())} handlers")
