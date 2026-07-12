"""Base Pydantic model shared by all configuration models."""

import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


class FlexibleModel(BaseModel):
    """Base model with environment variable substitution.

    All string values in configuration files support `${VAR}` syntax for
    environment variable expansion:

    ```yaml
    project_information:
      project_name: ${PROJECT_PREFIX}_design
    ```

    Variables are expanded at load time. If a variable is not set,
    the literal `${VAR}` string is preserved. Callers may pass a
    validation context (``model_validate(data, context={"env": {...}})``)
    to make additional variables available; those take precedence over
    ``os.environ`` for this validation only.
    """

    model_config = ConfigDict(
        extra="allow", validate_assignment=True, str_strip_whitespace=True
    )

    @field_validator("*", mode="before")
    @classmethod
    def substitute_env_vars(cls, v: Any, info: ValidationInfo) -> Any:
        """Replace ${VAR} with environment variable values."""
        if isinstance(v, str):
            context_env = (info.context or {}).get("env", {})
            env = {**os.environ, **context_env}
            return re.sub(
                r"\$\{([A-Z_][A-Z0-9_]*)\}",
                lambda m: env.get(m.group(1), m.group(0)),
                v,
            )
        elif isinstance(v, dict):
            return {k: cls.substitute_env_vars(val, info) for k, val in v.items()}
        elif isinstance(v, list):
            return [cls.substitute_env_vars(item, info) for item in v]
        return v
