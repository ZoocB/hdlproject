"""Unit tests for the StepTracker state machine.

These feed parsed-line sequences (via the real parser + the build handler's step
patterns, mirroring production) into a tracker wired to a recording fake sink,
and assert both the emitted sink calls and the final BuildOutcome. This is the
behavioural lock for the Phase-1c extraction out of VivadoOutputProcessor.
"""

import logging

from hdlproject.core.step_tracker import StepTracker
from hdlproject.handlers.build import BuildHandler
from hdlproject.utils.vivado_output_parser import VivadoOutputParser


class RecordingSink:
    """Captures every ProgressSink call as a (method, args) tuple."""

    def __init__(self):
        self.calls: list[tuple] = []

    def start_project(self, project_name):
        self.calls.append(("start_project", project_name))

    def update_project_step(self, project_name, step_name, failed=False, message=None,
                            warning_count=0, critical_warning_count=0, error_count=0,
                            step_result=None):
        self.calls.append(
            ("update_project_step", step_name, failed, step_result,
             warning_count, critical_warning_count, error_count)
        )

    def complete_project(self, project_name, success=True, message=None):
        self.calls.append(("complete_project", success, message))

    def set_project_context_name(self, project_name, context_name):
        self.calls.append(("set_project_context_name", context_name))

    def set_build_artefacts_path(self, project_name, artefacts_path):
        self.calls.append(("set_build_artefacts_path", artefacts_path))

    def set_extra_info(self, project_name, key, label, value, style="dim", path=None):
        self.calls.append(("set_extra_info", key, value, path))

    def process_output(self, line, project_name):
        self.calls.append(("process_output", line))


def _run(lines: list[str]):
    parser = VivadoOutputParser(BuildHandler.CONFIG.step_patterns)
    sink = RecordingSink()
    tracker = StepTracker(
        project_name="proj",
        operation="build",
        sink=sink,
        project_logger=logging.getLogger("test.step_tracker"),
    )
    for line in lines:
        tracker.process(parser.parse_line(line), line)
    return tracker, sink


def _steps(sink, **filt):
    """Return update_project_step calls, optionally filtered by step name."""
    out = [c for c in sink.calls if c[0] == "update_project_step"]
    if "step" in filt:
        out = [c for c in out if c[1] == filt["step"]]
    return out


def test_clean_run_succeeds():
    tracker, sink = _run([
        "[HDLPROJECT_STEP_SUCCESS] handle_xcis::process_xcis",
        "Launching Runs -- Synthesis",
        "synth_design completed successfully",
    ])
    outcome = tracker.build_outcome(exit_code=0)
    assert outcome.success
    assert outcome.total_errors == 0
    assert not outcome.has_warnings
    # IP cores TCL step completed as success
    assert ("update_project_step", "Processing IP Cores", False, "success", 0, 0, 0) \
        in sink.calls


def test_tcl_step_error_fails_run():
    tracker, sink = _run([
        "[HDLPROJECT_STEP_ERROR] handle_bds::process_bds [W:1 E:3]",
    ])
    outcome = tracker.build_outcome(exit_code=0)
    assert not outcome.success
    assert outcome.error_lines == ["TCL step failed: Processing Block Designs"]
    assert "TCL step error" in outcome.failure_message
    # counts from the marker propagate to totals
    assert outcome.total_errors == 3
    assert outcome.total_warnings == 1


def test_vivado_errors_counted_only_outside_tcl_steps():
    # A SUCCESS marker completes the TCL step immediately (it is not a start),
    # so the following ERROR occurs with no active step and is counted.
    tracker, _ = _run([
        "[HDLPROJECT_STEP_SUCCESS] handle_xcis::process_xcis",
        "ERROR: [foo] this happens with no active step",
    ])
    # The ERROR occurs while no Vivado phase is active -> counted (no tcl step open)
    outcome = tracker.build_outcome(exit_code=0)
    assert outcome.total_errors == 1
    assert not outcome.success


def test_vivado_phase_accumulates_warnings():
    tracker, sink = _run([
        "Launching Runs -- Synthesis",
        "WARNING: [Synth 8-1] unconnected port",
        "CRITICAL WARNING: [Synth 8-2] no clock",
        "synth_design completed successfully",
    ])
    outcome = tracker.build_outcome(exit_code=0)
    assert outcome.success  # warnings do not fail the run
    assert outcome.has_warnings
    assert outcome.total_warnings == 1
    assert outcome.total_critical_warnings == 1
    # Synthesis step reported as warning with the accumulated counts
    synth = _steps(sink, step="Synthesis")
    assert synth[-1] == ("update_project_step", "Synthesis", False, "warning", 1, 1, 0)


def test_timing_failure_fails_run_and_sets_extra_info():
    tracker, sink = _run([
        "[HDLPROJECT_TIMING_RESULT] status=FAILED report=/tmp/t.rpt",
    ])
    outcome = tracker.build_outcome(exit_code=0)
    assert not outcome.success
    assert outcome.timing_failed
    assert "timing" in outcome.failure_message
    assert ("set_extra_info", "timing", "FAILED", "/tmp/t.rpt") in sink.calls


def test_nonzero_exit_fails_clean_run():
    tracker, _ = _run(["Launching Runs -- Synthesis", "synth_design completed"])
    outcome = tracker.build_outcome(exit_code=1)
    assert not outcome.success
    assert "exit code 1" in outcome.failure_message


def test_context_and_artefacts_forwarded():
    _, sink = _run([
        "[HDLPROJECT_PROJECT_CONTEXT] name=MY_BUILD",
        "[HDLPROJECT_BUILD_ARTEFACTS] /out/artefacts",
    ])
    assert ("set_project_context_name", "MY_BUILD") in sink.calls
    assert ("set_build_artefacts_path", "/out/artefacts") in sink.calls


def test_incomplete_vivado_step_finalised_on_failure():
    tracker, sink = _run([
        "Command: write_bitstream",
        "ERROR: [DRC 1] something bad",
    ])
    # Process died mid-phase
    tracker.finalise_incomplete_step(process_failed=True)
    outcome = tracker.build_outcome(exit_code=1)
    assert not outcome.success
    # The incomplete Writing Bitstream step was reported as a failed error step
    wb = _steps(sink, step="Writing Bitstream")
    assert wb[-1][2] is True  # failed
    assert wb[-1][3] == "error"
