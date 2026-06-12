"""Tool-backend interface and registry.

A :class:`ToolBackend` provides the two tool-specific pieces the executor needs:

1. ``generate_scripts`` — render/copy the tool's scripts for an operation into
   the operation directory and return the entry-point script path.
2. ``batch_invocation`` / ``gui_invocation`` — the executable arguments to run
   that entry point (or open a project) for this tool.

Everything else — shell/Docker wrapping, output streaming, cancellation,
parsing — is tool-agnostic and lives in the execution core.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from hdlproject.models.resolved import ResolvedOperationPaths, ResolvedProjectConfig
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ToolBackend(ABC):
    """A pluggable HDL tool backend (Vivado, and later Quartus, etc.)."""

    #: Tool identifier, matched against ``ResolvedProjectConfig.tool``.
    name: str

    @abstractmethod
    def generate_scripts(
        self,
        resolved_config: ResolvedProjectConfig,
        operation_paths: ResolvedOperationPaths,
        mode: str,
        cores: int = 1,
        build_steps: Optional[list[str]] = None,
    ) -> Path:
        """Generate this tool's scripts for ``mode`` and return the entry point.

        Implementations write their scripts into ``operation_paths.operation_dir``
        and return the path the executable should be pointed at.
        """

    @abstractmethod
    def batch_invocation(self, entry_point: Path) -> list[str]:
        """Executable arguments to run ``entry_point`` non-interactively."""

    @abstractmethod
    def gui_invocation(self, project_path: Path) -> list[str]:
        """Executable arguments to open ``project_path`` in the tool's GUI."""


_BACKENDS: dict[str, ToolBackend] = {}


def register_backend(backend: ToolBackend) -> None:
    """Register a backend under its ``name`` (last registration wins)."""
    _BACKENDS[backend.name] = backend
    logger.debug(f"Registered tool backend: {backend.name}")


def _load_builtin_backends() -> None:
    """Import built-in backend modules for their registration side effects."""
    from hdlproject.backends import vivado  # noqa: F401


def get_tool_backend(tool: str) -> ToolBackend:
    """Return the registered backend for ``tool``.

    Raises:
        ValueError: if no backend is registered for the tool.
    """
    if not _BACKENDS:
        _load_builtin_backends()

    backend = _BACKENDS.get(tool)
    if backend is None:
        available = ", ".join(sorted(_BACKENDS)) or "none"
        raise ValueError(
            f"No tool backend registered for '{tool}'. Available: {available}"
        )
    return backend
