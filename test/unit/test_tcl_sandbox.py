"""The user-template Jinja2 environment is sandboxed.

``artefact_name`` and ``generated_sources`` templates come from user config, so
they are rendered through a SandboxedEnvironment. Legitimate dotted access and
filters must still work; attribute-traversal injection must be blocked.
"""

import pytest
from jinja2.exceptions import SecurityError

from hdlproject.core.tcl_generator import TclGenerator


@pytest.fixture
def env():
    return TclGenerator()._user_env


def test_legitimate_template_renders(env):
    out = env.from_string(
        "{{ project_information.project_name | upper }}_v{{ build_variables.major }}"
    ).render(
        project_information={"project_name": "adder"},
        build_variables={"major": 2},
    )
    assert out == "ADDER_v2"


def test_attribute_traversal_injection_blocked(env):
    with pytest.raises(SecurityError):
        env.from_string("{{ ''.__class__.__mro__ }}").render()


def test_call_to_dunder_blocked(env):
    with pytest.raises(SecurityError):
        env.from_string("{{ cycler.__init__.__globals__ }}").render(cycler=object())
