"""Tests for the pluggable tool-backend registry.

Locks the infrastructure that lets a new HDL tool be added without touching the
executor: backend lookup by tool name, the Vivado backend's exact invocation
arguments (behaviour-identical to the previous inline handling), and a clear
error for an unknown tool.
"""

from pathlib import Path

import pytest

from hdlproject.backends import ToolBackend, get_tool_backend, register_backend
from hdlproject.backends.vivado import VivadoBackend


def test_vivado_backend_is_registered():
    backend = get_tool_backend("vivado")
    assert isinstance(backend, VivadoBackend)
    assert isinstance(backend, ToolBackend)
    assert backend.name == "vivado"


def test_vivado_batch_invocation_args():
    backend = get_tool_backend("vivado")
    args = backend.batch_invocation(Path("/work/op/tcl/project_workflow.tcl"))
    assert args == [
        "-mode", "batch", "-notrace",
        "-source", "/work/op/tcl/project_workflow.tcl",
    ]


def test_vivado_gui_invocation_args():
    backend = get_tool_backend("vivado")
    args = backend.gui_invocation(Path("/work/op/project/adder.xpr"))
    assert args == ["-mode", "gui", "-notrace", "/work/op/project/adder.xpr"]


def test_unknown_tool_raises_helpful_error():
    with pytest.raises(ValueError) as exc:
        get_tool_backend("quartus")
    assert "quartus" in str(exc.value)
    assert "vivado" in str(exc.value)  # lists what *is* available


def test_register_backend_makes_tool_available():
    class DummyBackend(ToolBackend):
        name = "dummy-test-tool"

        def generate_scripts(self, resolved_config, operation_paths, mode,
                             cores=1, build_steps=None):
            return Path("/tmp/dummy.tcl")

        def batch_invocation(self, entry_point):
            return ["--run", str(entry_point)]

        def gui_invocation(self, project_path):
            return ["--open", str(project_path)]

    register_backend(DummyBackend())
    got = get_tool_backend("dummy-test-tool")
    assert got.batch_invocation(Path("/x")) == ["--run", "/x"]
