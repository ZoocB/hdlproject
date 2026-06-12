"""Handler registry for managing available handlers.

This module provides a registry for handlers and their metadata.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Type

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


@dataclass
class HandlerInfo:
    """Handler registration information.

    Contains all metadata needed to instantiate and use a handler.
    """

    name: str
    handler_class: Type
    options_class: Type
    description: str
    menu_name: str
    cli_arguments: list[dict[str, Any]]
    supports_multiple: bool = True
    artefact_definitions: list = field(default_factory=list)

    def create_handler(self, environment: Any, interactive: bool = False):
        """Create handler instance with environment.

        Args:
            environment: RuntimeEnvironment instance
            interactive: Whether running in interactive mode

        Returns:
            Handler instance
        """
        return self.handler_class(environment=environment, interactive=interactive)

    def create_options(self, **kwargs):
        """Create options instance with only valid parameters.

        Args:
            **kwargs: Option parameters

        Returns:
            Options instance
        """
        import inspect

        sig = inspect.signature(self.options_class)
        valid_params = set(sig.parameters.keys())
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        return self.options_class(**filtered_kwargs)


class HandlerRegistry:
    """Registry for managing handlers."""

    def __init__(self):
        self._handlers: dict[str, HandlerInfo] = {}

    def register(self, info: HandlerInfo) -> None:
        """Register a handler.

        Args:
            info: Handler information
        """
        if info.name in self._handlers:
            logger.warning(f"Handler '{info.name}' already registered, overwriting")

        self._handlers[info.name] = info
        logger.debug(f"Registered handler: {info.name}")

    def get(self, name: str) -> Optional[HandlerInfo]:
        """Get handler info by name.

        Args:
            name: Handler name

        Returns:
            HandlerInfo or None if not found
        """
        return self._handlers.get(name)

    def get_all(self) -> dict[str, HandlerInfo]:
        """Get all registered handlers.

        Returns:
            Dictionary of handler name to HandlerInfo
        """
        return self._handlers.copy()

    def get_menu_handlers(
        self,
        for_multiple_projects: bool = False,
    ) -> list[tuple[str, HandlerInfo]]:
        """Get handlers suitable for menu display.

        Args:
            for_multiple_projects: Filter to only multi-project handlers

        Returns:
            List of (name, info) tuples sorted by menu_name
        """
        handlers = []

        for name, info in self._handlers.items():
            if for_multiple_projects and not info.supports_multiple:
                continue
            handlers.append((name, info))

        return sorted(handlers, key=lambda x: x[1].menu_name)


# Global registry instance
_registry = HandlerRegistry()


def register_handler(info: HandlerInfo) -> None:
    """Register a handler in the global registry.

    Args:
        info: Handler information
    """
    _registry.register(info)


def get_handler(name: str) -> Optional[HandlerInfo]:
    """Get handler from global registry.

    Args:
        name: Handler name

    Returns:
        HandlerInfo or None if not found
    """
    return _registry.get(name)


def get_all_handlers() -> dict[str, HandlerInfo]:
    """Get all handlers from global registry.

    Returns:
        Dictionary of handler name to HandlerInfo
    """
    return _registry.get_all()


def get_menu_handlers(
    for_multiple_projects: bool = False,
) -> list[tuple[str, HandlerInfo]]:
    """Get menu handlers from global registry.

    Args:
        for_multiple_projects: Filter to only multi-project handlers

    Returns:
        List of (name, info) tuples
    """
    return _registry.get_menu_handlers(for_multiple_projects)


def load_all_handlers():
    """Load all handler modules to trigger registration (import side effects)."""
    from hdlproject.handlers import (
        build,  # noqa: F401
        export,  # noqa: F401
        open_project,  # noqa: F401
        publish,  # noqa: F401
    )

    logger.debug(f"Loaded {len(_registry.get_all())} handlers")
