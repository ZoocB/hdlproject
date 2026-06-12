"""Pluggable HDL tool backends.

A tool backend encapsulates everything tool-specific about turning a resolved
project into a runnable process: how its scripts are generated (the TCL/Jinja2
templates today) and how the tool executable is invoked. The execution core
(``ToolExecutorService``) talks only to the :class:`ToolBackend` interface and
picks the implementation by ``ResolvedProjectConfig.tool``, so adding a new tool
(e.g. Quartus) means adding a backend — not changing the executor or handlers.

Vivado is the only backend today.
"""

from hdlproject.backends.base import (
    ToolBackend,
    get_tool_backend,
    register_backend,
)

__all__ = ["ToolBackend", "get_tool_backend", "register_backend"]
