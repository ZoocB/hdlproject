"""Targeted parser unit tests (complement the golden snapshot).

The golden test locks the parser's decisions on a representative log. These add
focused, named assertions for the finicky bits — count extraction, false-positive
suppression, critical-vs-regular warning precedence, and marker extraction — so a
regression points at the specific rule that broke.
"""

import pytest

from hdlproject.utils.vivado_output_parser import (
    MessageType,
    StepPattern,
    StepResultType,
    VivadoOutputParser,
)


@pytest.fixture
def parser():
    return VivadoOutputParser(
        [StepPattern.tcl("Block Designs", "handle_bds::process_bds")]
    )


def test_plain_parser_severity_classification():
    p = VivadoOutputParser()
    assert p.parse_line("ERROR: [x] boom").type == MessageType.ERROR
    cw = p.parse_line("CRITICAL WARNING: [x] hmm")
    assert cw.type == MessageType.CRITICAL_WARNING
    assert p.parse_line("WARNING: [x] eh").type == MessageType.WARNING
    assert p.parse_line("INFO: [x] fyi").type == MessageType.INFO


def test_critical_warning_not_misread_as_warning():
    p = VivadoOutputParser()
    # 'CRITICAL WARNING' contains 'WARNING' but must classify as critical.
    assert p.parse_line("CRITICAL WARNING: foo").type == MessageType.CRITICAL_WARNING


@pytest.mark.parametrize(
    "line",
    [
        "set error_msg to something",
        "no error here",
        "incremented error_count by one",
        "warning_msg is unset",
        "no warning produced",
    ],
)
def test_false_positives_classified_as_info(line):
    p = VivadoOutputParser()
    assert p.parse_line(line).type == MessageType.INFO


def test_tcl_marker_count_extraction(parser):
    msg = parser.parse_line("[HDLPROJECT_STEP_ERROR] handle_bds::process_bds [W:4 E:2]")
    assert msg.type == MessageType.STEP_UPDATE
    assert msg.step_result == StepResultType.ERROR
    assert msg.is_failure is True
    assert msg.is_tcl_step is True
    assert msg.warning_count == 4
    assert msg.error_count == 2


def test_tcl_success_marker_has_no_failure(parser):
    msg = parser.parse_line("[HDLPROJECT_STEP_SUCCESS] handle_bds::process_bds")
    assert msg.step_result == StepResultType.SUCCESS
    assert msg.is_failure is False


def test_timing_marker_parsed():
    p = VivadoOutputParser()
    passed = p.parse_line("[HDLPROJECT_TIMING_RESULT] status=PASSED report=/a/b.rpt")
    assert passed.type == MessageType.TIMING_RESULT
    assert passed.timing_passed is True
    assert passed.timing_report_path == "/a/b.rpt"

    failed = p.parse_line("[HDLPROJECT_TIMING_RESULT] status=FAILED report=/c.rpt")
    assert failed.timing_passed is False


def test_project_context_and_artefacts_markers():
    p = VivadoOutputParser()
    ctx = p.parse_line("[HDLPROJECT_PROJECT_CONTEXT] name=MY_BUILD")
    assert ctx.type == MessageType.PROJECT_CONTEXT
    assert ctx.project_context_name == "MY_BUILD"

    art = p.parse_line("[HDLPROJECT_BUILD_ARTEFACTS] /out/x")
    assert art.type == MessageType.BUILD_ARTEFACTS
    assert art.build_artefacts_path == "/out/x"


def test_vivado_phase_start_and_complete():
    p = VivadoOutputParser([
        StepPattern.start("Synthesis", r"Launching Runs -- Synthesis"),
        StepPattern.complete("Synthesis", r"synth_design completed"),
        StepPattern.failed("Synthesis", r"synth_design failed"),
    ])
    start = p.parse_line("Launching Runs -- Synthesis")
    assert start.is_step_start is True
    assert start.is_tcl_step is False

    done = p.parse_line("synth_design completed")
    assert done.step_result == StepResultType.SUCCESS
    assert done.is_failure is False

    fail = p.parse_line("synth_design failed")
    assert fail.step_result == StepResultType.ERROR
    assert fail.is_failure is True
