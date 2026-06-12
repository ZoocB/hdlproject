"""Schema-freeze guard for the configuration models.

The YAML configuration interface is near-frozen: refactors of the model layer
(notably the Phase-1b split of ``models.py`` into submodules) must not change the
user-facing schema. This test compares the live Pydantic JSON schema of the two
top-level config models against a committed baseline. JSON schema is deterministic
(unlike the prose doc generator) and captures field names, types, defaults, and
required-ness precisely.

If the schema changes *intentionally* (an additive, optional field), regenerate
the baseline and review the diff to confirm the change is additive/optional::

    python test/unit/test_schema_freeze.py
"""

import json
from pathlib import Path

from hdlproject.models import GlobalConfiguration, ProjectConfiguration

BASELINE = Path(__file__).parent.parent / "fixtures" / "config_schema.baseline.json"


def _current_schema() -> str:
    schema = {
        "GlobalConfiguration": GlobalConfiguration.model_json_schema(),
        "ProjectConfiguration": ProjectConfiguration.model_json_schema(),
    }
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def test_config_schema_matches_baseline():
    assert _current_schema() == BASELINE.read_text(), (
        "Config JSON schema differs from the frozen baseline. If this change is "
        "intentional and additive/optional, regenerate the baseline (see module "
        "docstring)."
    )


if __name__ == "__main__":
    BASELINE.write_text(_current_schema())
    print(f"Wrote schema baseline: {BASELINE}")
