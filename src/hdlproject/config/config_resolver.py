"""YAML configuration loading with inheritance support.

This module handles only the YAML loading and inheritance processing.
Pydantic validation is done by the ConfigLoader after inheritance is resolved.
"""

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class YAMLConfigLoader:
    """YAML configuration loader with inheritance support.

    Processes the 'inherits' key to merge parent configurations before
    returning the raw dict for Pydantic validation.
    """

    def load_with_inheritance(self, config_path: Path) -> dict[str, Any]:
        """Load configuration with inheritance processing.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            Merged configuration dict with inheritance resolved

        Raises:
            ValueError: If file is not YAML
            FileNotFoundError: If config file or parent doesn't exist
            RuntimeError: If circular dependency detected
        """
        return self._load_recursive(config_path, set(), set())

    def _load_recursive(
        self,
        config_path: Path,
        visited: set[str],
        merged: set[str],
    ) -> dict[str, Any]:
        """Recursively load configuration with inheritance.

        Args:
            config_path: Path to configuration file
            visited: Paths visited along the current inheritance path, used
                to detect genuine cycles.
            merged: Paths already merged into the result anywhere in this
                call's traversal, so a shared ancestor reached via multiple
                branches (diamond inheritance) is only merged once.

        Returns:
            Merged configuration dict
        """
        # Check for circular dependencies
        abs_path = str(config_path.absolute())
        if abs_path in visited:
            raise RuntimeError(f"Circular dependency detected: {abs_path}")
        visited.add(abs_path)

        # Validate file extension
        if config_path.suffix not in [".yaml", ".yml"]:
            raise ValueError(
                f"Only YAML configuration files are supported. Found: {config_path}"
            )

        # Load file
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}"
            ) from e
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML file {config_path}: {e}")
            raise ValueError(f"Invalid YAML in {config_path}: {e}") from e

        # Process inheritance
        if "inherits" in data:
            inherits = data.pop("inherits")
            if isinstance(inherits, str):
                inherits = [inherits]

            # Start with empty base
            result = {}

            # Load each parent
            for parent_file in inherits:
                parent_path = (config_path.parent / parent_file).resolve()
                if not parent_path.exists():
                    raise FileNotFoundError(
                        f"Parent configuration not found: {parent_path}\n"
                        f"  Referenced from: {config_path}"
                    )
                parent_abs = str(parent_path.absolute())
                if parent_abs in merged:
                    # Already merged via another branch of this inheritance
                    # tree (diamond inheritance): first occurrence wins.
                    continue
                parent_data = self._load_recursive(
                    parent_path, visited.copy(), merged
                )
                merged.add(parent_abs)
                result = self._merge_configs(result, parent_data)

            # Merge current file on top
            return self._merge_configs(result, data)

        return data

    def _merge_configs(
        self,
        base: dict[str, Any],
        override: dict[str, Any],
        path: str = "",
    ) -> dict[str, Any]:
        """Deep merge configurations with smart handling.

        Merge behavior:
        - Lists: Append (parent items first, then child items)
        - Dicts: Recursive merge
        - Scalars: ERROR if defined in both parent and child

        Args:
            base: Parent configuration dict
            override: Child configuration dict
            path: Current path in config tree (for error messages)

        Returns:
            Merged configuration dict

        Raises:
            ValueError: If scalar value defined in both parent and child
        """
        result = deepcopy(base)

        for key, value in override.items():
            current_path = f"{path}.{key}" if path else key

            if key in result:
                # Both are lists: append
                if isinstance(result[key], list) and isinstance(value, list):
                    result[key] = result[key] + deepcopy(value)
                # Both are dicts: recursive merge
                elif isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._merge_configs(result[key], value, current_path)
                # Scalar or type mismatch: error
                else:
                    raise ValueError(
                        f"Duplicate definition of '{current_path}' found in inheritance chain. "
                        f"Parent value: {result[key]}, Child value: {value}. "
                        f"Scalar values should only be defined once across inherited configurations."
                    )
            else:
                # Key doesn't exist in base, just add it
                result[key] = deepcopy(value)

        return result
