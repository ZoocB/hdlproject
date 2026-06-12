"""Tests for YAML configuration inheritance + merging.

Locks the behaviour of ``ConfigLoader`` against the committed ``test/prj``
inheritance fixtures, so the Phase-1b ``models.py`` split (and any config
refactor) cannot silently change how project configs resolve.

The ``test/`` directory doubles as a self-contained repository root: it has its
own ``hdlproject_global_config.yaml`` and a ``prj/`` tree with two projects that
inherit shared ``configs/*.yaml`` files.
"""

from pathlib import Path

import pytest

from hdlproject.config.loader import ConfigLoader

TEST_ROOT = Path(__file__).parent.parent


@pytest.fixture
def loader() -> ConfigLoader:
    return ConfigLoader(TEST_ROOT)


def test_global_config_loads(loader):
    gc = loader.load_global_config()
    assert gc.project_dir == "prj"
    assert gc.default_cores == 2
    assert gc.max_parallel_builds == 2


def test_project_overrides_win_over_inherited(loader):
    """Child project values take precedence; inherited values fill the rest."""
    cfg = loader.load_project_config("project_1")
    info = cfg.project_information

    # From the project file itself
    assert info.project_name == "adder_project_1"
    assert info.top_level_file_name == "adder_top"

    # Inherited from configs/arty_z7_device.yaml
    assert info.tool == "vivado"
    assert info.tool_version == "2023.2"
    assert info.device_info.part_name == "xc7z020clg400-1"
    assert info.device_info.board_name == "Arty_Z7_20"


def test_inherited_lists_and_dicts_merge(loader):
    cfg = loader.load_project_config("project_1")

    # constraints list comes wholesale from configs/common_build.yaml
    files = [c.file for c in cfg.constraints]
    assert files == [
        "../../files/constraints/pins_arty_z7.xdc",
        "../../files/constraints/timing.xdc",
    ]

    # synth_options dict inherited from common_build.yaml
    assert cfg.synth_options["STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY"] == "rebuilt"

    # build_variables defined in the project file
    bv = cfg.build_configuration.build_variables
    assert bv["version_major"].value == 1
    assert bv["version_minor"].value == 0
    assert bv["git_hash"].command == "git rev-parse --short HEAD"

    # artefact_name template inherited from common_build.yaml (left unrendered here)
    assert "project_name" in cfg.build_configuration.artefact_name


def test_two_projects_resolve_independently(loader):
    """project_2 overrides build_variables and adds impl_options of its own."""
    p2 = loader.load_project_config("project_2")
    assert p2.project_information.project_name == "adder_project_2"
    assert p2.build_configuration.build_variables["version_major"].value == 2
    assert p2.impl_options["STEPS.OPT_DESIGN.ARGS.DIRECTIVE"] == "Explore"
    # project_2 still inherits the shared device info
    assert p2.project_information.device_info.part_name == "xc7z020clg400-1"
