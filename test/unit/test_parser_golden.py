"""Golden tests that lock the current Vivado output parser behaviour.

These exist so the Phase-1c extraction of the step state machine (and any later
parser change) is *behaviour-preserving*: the parser is finicky by necessity
(Vivado output has caused real problems), so we snapshot its exact decisions on a
representative log and assert they never drift unintentionally.

If a change to the parser is *intended*, regenerate the golden with::

    python -m test.unit.test_parser_golden

and review the diff carefully before committing.
"""

import json
from pathlib import Path

from hdlproject.handlers.build import BuildHandler
from hdlproject.utils.vivado_output_parser import VivadoOutputParser

_LOGS = Path(__file__).parent.parent / "fixtures" / "vivado_logs"
FIXTURE_LOG = _LOGS / "build_mixed.log"
GOLDEN = _LOGS / "build_mixed.golden.json"


def _serialise(parsed) -> dict:
    """Serialise a ParsedMessage to only its meaningful (non-default) fields."""
    out: dict = {"type": parsed.type.name, "message": parsed.message}
    if parsed.step_name is not None:
        out["step_name"] = parsed.step_name
    if parsed.is_failure:
        out["is_failure"] = True
    if parsed.step_result is not None:
        out["step_result"] = parsed.step_result.value
    if parsed.warning_count:
        out["warning_count"] = parsed.warning_count
    if parsed.critical_warning_count:
        out["critical_warning_count"] = parsed.critical_warning_count
    if parsed.error_count:
        out["error_count"] = parsed.error_count
    if parsed.project_context_name is not None:
        out["project_context_name"] = parsed.project_context_name
    if parsed.build_artefacts_path is not None:
        out["build_artefacts_path"] = parsed.build_artefacts_path
    if parsed.is_step_start:
        out["is_step_start"] = True
    if parsed.is_tcl_step:
        out["is_tcl_step"] = True
    if parsed.timing_passed is not None:
        out["timing_passed"] = parsed.timing_passed
    if parsed.timing_report_path is not None:
        out["timing_report_path"] = parsed.timing_report_path
    return out


def _parse_fixture() -> list[dict]:
    parser = VivadoOutputParser(BuildHandler.CONFIG.step_patterns)
    lines = FIXTURE_LOG.read_text().splitlines()
    return [_serialise(parser.parse_line(line)) for line in lines]


def test_parser_matches_golden():
    assert GOLDEN.exists(), "Golden snapshot missing - run module directly to create it"
    expected = json.loads(GOLDEN.read_text())
    actual = _parse_fixture()
    assert actual == expected


if __name__ == "__main__":
    GOLDEN.write_text(json.dumps(_parse_fixture(), indent=2) + "\n")
    print(f"Wrote golden snapshot: {GOLDEN}")
