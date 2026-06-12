"""Vivado tool backend.

Wraps the existing Jinja2/TCL generator and provides Vivado's command-line
invocation. This is the reference implementation of :class:`ToolBackend`; its
behaviour is identical to the previous inline Vivado handling in the executor.
"""

from pathlib import Path
from typing import Optional

from hdlproject.backends.base import ToolBackend, register_backend
from hdlproject.core.tcl_generator import TclGenerator
from hdlproject.models.resolved import ResolvedOperationPaths, ResolvedProjectConfig


class VivadoBackend(ToolBackend):
    """Backend that drives Xilinx Vivado in batch (`-source`) and GUI modes."""

    name = "vivado"

    def __init__(self) -> None:
        # TclGenerator is stateless across calls (templates + variable resolver),
        # so a single instance is reused for every operation.
        self._generator = TclGenerator()

    def generate_scripts(
        self,
        resolved_config: ResolvedProjectConfig,
        operation_paths: ResolvedOperationPaths,
        mode: str,
        cores: int = 1,
        build_steps: Optional[list[str]] = None,
    ) -> Path:
        return self._generator.generate(
            resolved_config=resolved_config,
            operation_paths=operation_paths,
            mode=mode,
            cores=cores,
            build_steps=build_steps,
        )

    def batch_invocation(self, entry_point: Path) -> list[str]:
        return ["-mode", "batch", "-notrace", "-source", str(entry_point)]

    def gui_invocation(self, project_path: Path) -> list[str]:
        return ["-mode", "gui", "-notrace", str(project_path)]


register_backend(VivadoBackend())
