"""Tests for scoped (per-project) environment_setup handling.

Locks two properties introduced to fix cross-project env leakage and
build-parallelism races:

- ${VAR} expansion in a project's own config fields still sees the
  variables its own environment_setup script exports.
- Those variables are captured and threaded through explicitly (validation
  context, then ResolvedProjectConfig.environment) instead of being written
  into the process-global os.environ.
"""

import os
import stat
from pathlib import Path

import pytest

from hdlproject.config.loader import ConfigLoader

GLOBAL_CONFIG_YAML = """\
project_dir: "prj"
tools:
  vivado:
    "2020.1":
      executable: "vivado"
"""

PROJECT_CONFIG_YAML = """\
project_information:
  project_name: myproject
  top_level_file_name: top
  tool: vivado
  tool_version: "2020.1"
  device_info:
    part_name: xc7z020clg400-1
    board_name: TestBoard
environment_setup:
  bash: setup.sh
synth_options:
  TEST_KEY: "${FOO}_suffix"
"""


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """A self-contained repository root with one project that exports FOO=bar."""
    (tmp_path / "hdlproject_global_config.yaml").write_text(GLOBAL_CONFIG_YAML)

    project_dir = tmp_path / "prj" / "myproject"
    project_dir.mkdir(parents=True)
    (project_dir / "hdlproject_project_config.yaml").write_text(PROJECT_CONFIG_YAML)

    script_path = project_dir / "setup.sh"
    script_path.write_text("#!/bin/sh\necho 'FOO=bar'\n")
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    return tmp_path


def test_env_setup_var_expanded_in_own_config(repo_root: Path):
    """${FOO} in the project's own config is expanded from its setup script."""
    assert "FOO" not in os.environ

    loader = ConfigLoader(repo_root)
    config = loader.load_project_config("myproject")

    assert config.synth_options["TEST_KEY"] == "bar_suffix"


def test_env_setup_does_not_leak_into_os_environ(repo_root: Path):
    """Loading a project must not mutate the process-global os.environ."""
    assert "FOO" not in os.environ

    loader = ConfigLoader(repo_root)
    loader.load_project_config("myproject")

    assert "FOO" not in os.environ


def test_captured_env_lands_on_resolved_config(repo_root: Path):
    """The captured KEY=VALUE pairs flow through to ResolvedProjectConfig."""
    loader = ConfigLoader(repo_root)
    resolved = loader.resolve_project_config("myproject")

    assert resolved.environment == {"FOO": "bar"}
    assert "FOO" not in os.environ


def test_project_without_environment_setup_is_unaffected(tmp_path: Path):
    """A project with no environment_setup behaves exactly as before."""
    (tmp_path / "hdlproject_global_config.yaml").write_text(GLOBAL_CONFIG_YAML)

    project_dir = tmp_path / "prj" / "plain"
    project_dir.mkdir(parents=True)
    (project_dir / "hdlproject_project_config.yaml").write_text(
        """\
project_information:
  project_name: plainproject
  top_level_file_name: top
  tool: vivado
  tool_version: "2020.1"
  device_info:
    part_name: xc7z020clg400-1
    board_name: TestBoard
"""
    )

    loader = ConfigLoader(tmp_path)
    config = loader.load_project_config("plain")
    resolved = loader.resolve_project_config("plain")

    assert config.environment_setup is None
    assert resolved.environment == {}
