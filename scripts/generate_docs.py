#!/usr/bin/env python3
"""Generate YAML configuration documentation from Pydantic models.

All content comes from models.py:
- Module docstring: overview documentation
- Class docstrings: model descriptions with examples
- Field definitions: auto-generated tables

This script also generates a complete example YAML at the end using dummy values.
"""

import argparse
import inspect
import sys
from pathlib import Path
from typing import Any, get_args, get_origin, Union

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from pydantic import BaseModel
from pydantic.fields import FieldInfo


class DummyValueGenerator:
    """Generates dummy values for YAML examples."""

    def __init__(self):
        self.counters = {}

    def _next(self, prefix: str) -> int:
        count = self.counters.get(prefix, 0)
        self.counters[prefix] = count + 1
        return count

    def generate(self, annotation: Any, field_name: str, indent: int = 0) -> str:
        """Generate YAML for a field with dummy values."""
        spaces = "  " * indent

        if annotation is None or annotation is type(None):
            return f"{spaces}{field_name}: null"

        origin = get_origin(annotation)
        args = get_args(annotation)

        # Handle Optional[X] - unwrap and generate
        if origin is Union or str(origin) == "typing.Union":
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return self.generate(non_none[0], field_name, indent)
            return f"{spaces}{field_name}: null"

        # Handle list[X]
        if origin is list:
            lines = [f"{spaces}{field_name}:"]
            item_type = args[0] if args else str
            for i in range(2):
                item_val = self._generate_value(
                    item_type, f"{field_name}_item", indent + 1, is_list_item=True
                )
                lines.append(item_val)
            return "\n".join(lines)

        # Handle dict[K, V]
        if origin is dict:
            lines = [f"{spaces}{field_name}:"]
            val_type = args[1] if len(args) > 1 else str
            for i in range(2):
                key = f"my_{field_name}_key_{i}"
                if isinstance(val_type, type) and issubclass(val_type, BaseModel):
                    lines.append(f"{spaces}  {key}:")
                    lines.append(self._generate_model(val_type, indent + 2))
                else:
                    val = self._scalar_value(val_type, field_name)
                    lines.append(f"{spaces}  {key}: {val}")
            return "\n".join(lines)

        # Handle nested Pydantic model
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            lines = [f"{spaces}{field_name}:"]
            lines.append(self._generate_model(annotation, indent + 1))
            return "\n".join(lines)

        # Scalar value
        val = self._scalar_value(annotation, field_name)
        return f"{spaces}{field_name}: {val}"

    def _generate_value(
        self, annotation: Any, name: str, indent: int, is_list_item: bool = False
    ) -> str:
        """Generate a single value (for list items or dict values)."""
        spaces = "  " * indent

        origin = get_origin(annotation)
        args = get_args(annotation)

        # Handle Optional
        if origin is Union or str(origin) == "typing.Union":
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return self._generate_value(non_none[0], name, indent, is_list_item)

        # Nested model in list
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if is_list_item:
                # First field on same line as dash
                model_yaml = self._generate_model_for_list(annotation, indent)
                return model_yaml
            return self._generate_model(annotation, indent)

        # Scalar
        val = self._scalar_value(annotation, name)
        if is_list_item:
            return f"{spaces}- {val}"
        return f"{spaces}{val}"

    def _generate_model(self, model: type[BaseModel], indent: int) -> str:
        """Generate YAML for a Pydantic model."""
        lines = []
        spaces = "  " * indent

        for name, field_info in model.model_fields.items():
            annotation = model.__annotations__.get(name, str)
            field_yaml = self.generate(annotation, name, indent)
            lines.append(field_yaml)

        return "\n".join(lines)

    def _generate_model_for_list(self, model: type[BaseModel], indent: int) -> str:
        """Generate YAML for a model as a list item (with leading dash)."""
        lines = []
        spaces = "  " * indent

        fields = list(model.model_fields.items())
        for i, (name, field_info) in enumerate(fields):
            annotation = model.__annotations__.get(name, str)

            if i == 0:
                # First field gets the dash
                inner_yaml = self.generate(annotation, name, 0).strip()
                lines.append(f"{spaces}- {inner_yaml}")
            else:
                # Subsequent fields are indented
                lines.append(self.generate(annotation, name, indent + 1))

        return "\n".join(lines)

    def _scalar_value(self, annotation: Any, name: str) -> str:
        """Generate a scalar dummy value."""
        n = self._next(name)

        if annotation is bool or annotation == bool:
            return "true" if n % 2 == 0 else "false"
        if annotation is int or annotation == int:
            return str(n)
        if annotation is float or annotation == float:
            return f"{n}.0"
        # Default to string
        return f'"my_{name}_{n}"'


def sort_by_dependencies(models: list[type[BaseModel]]) -> list[type[BaseModel]]:
    """Sort models so dependencies come before dependents."""
    model_names = {m.__name__ for m in models}
    model_map = {m.__name__: m for m in models}

    def get_deps(model: type[BaseModel]) -> set[str]:
        deps = set()
        for field_name in model.model_fields:
            annotation = model.__annotations__.get(field_name)
            deps.update(extract_refs(annotation, model_names))
        return deps

    def extract_refs(annotation: Any, valid: set[str]) -> set[str]:
        refs = set()
        if annotation is None:
            return refs
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if annotation.__name__ in valid:
                refs.add(annotation.__name__)
            return refs
        for arg in get_args(annotation):
            refs.update(extract_refs(arg, valid))
        return refs

    deps_map = {m.__name__: get_deps(m) for m in models}
    sorted_names, visited, temp = [], set(), set()

    def visit(name: str):
        if name in temp or name in visited:
            return
        temp.add(name)
        for dep in deps_map.get(name, set()):
            if dep in model_map:
                visit(dep)
        temp.discard(name)
        visited.add(name)
        sorted_names.append(name)

    for m in models:
        visit(m.__name__)
    return [model_map[n] for n in sorted_names]


def get_type_name(annotation: Any) -> str:
    """Convert type annotation to readable string."""
    if annotation is type(None):
        return "null"

    origin = get_origin(annotation)
    args = get_args(annotation)

    if str(origin) == "typing.Union" or origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return get_type_name(non_none[0])
        return " | ".join(get_type_name(a) for a in non_none)

    if origin is list:
        return f"list[{get_type_name(args[0])}]" if args else "list"

    if origin is dict:
        if args:
            return f"dict[{get_type_name(args[0])}, {get_type_name(args[1])}]"
        return "dict"

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return f"[{annotation.__name__}](#{annotation.__name__.lower()})"

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation)


def is_required(field_info: FieldInfo) -> bool:
    """Check if field is required."""
    from pydantic_core import PydanticUndefined

    return (
        field_info.default is PydanticUndefined and field_info.default_factory is None
    )


def get_default_repr(field_info: FieldInfo) -> str:
    """Get string representation of default value."""
    from pydantic_core import PydanticUndefined

    if field_info.default is not PydanticUndefined:
        return "null" if field_info.default is None else repr(field_info.default)
    if field_info.default_factory is not None:
        default = field_info.default_factory()
        if isinstance(default, dict) and not default:
            return "{}"
        if isinstance(default, list) and not default:
            return "[]"
        return repr(default)
    return "—"


def generate_field_table(model: type[BaseModel]) -> list[str]:
    """Generate markdown table for model fields."""
    if not model.model_fields:
        return []

    lines = [
        "| Field | Type | Required | Default | Description |",
        "|-------|------|----------|---------|-------------|",
    ]

    for name, field_info in model.model_fields.items():
        annotation = model.__annotations__.get(name, Any)
        req = "Yes" if is_required(field_info) else "No"
        default = "—" if is_required(field_info) else get_default_repr(field_info)
        desc = (field_info.description or "No description.").replace("|", "\\|")
        lines.append(
            f"| `{name}` | {get_type_name(annotation)} | {req} | `{default}` | {desc} |"
        )

    return lines


def generate_full_example(root_model: type[BaseModel], title: str) -> list[str]:
    """Generate a complete YAML example for a root model."""
    lines = [
        f"### {title}",
        "",
        "```yaml",
    ]

    generator = DummyValueGenerator()
    yaml_content = generator._generate_model(root_model, 0)
    lines.append(yaml_content)
    lines.append("```")
    lines.append("")

    return lines


def extract_sections_from_docstring(docstring: str) -> list[str]:
    """Extract ## section headers from module docstring."""
    sections = []
    for line in docstring.split("\n"):
        if line.startswith("## "):
            sections.append(line[3:].strip())
    return sections


def generate_toc(
    docstring_sections: list[str], models: list[type[BaseModel]]
) -> list[str]:
    """Generate table of contents."""
    lines = [
        "## Contents",
        "",
    ]

    # Sections from module docstring
    for section in docstring_sections:
        anchor = section.lower().replace(" ", "-")
        lines.append(f"- [{section}](#{anchor})")

    # Configuration Reference with sub-items for each model
    lines.append("- [Configuration Reference](#configuration-reference)")
    for model in models:
        anchor = model.__name__.lower()
        lines.append(f"  - [{model.__name__}](#{anchor})")

    # Complete Examples
    lines.append("- [Complete Examples](#complete-examples)")
    lines.append("")

    return lines


def generate_markdown(module_docstring: str, models: list[type[BaseModel]]) -> str:
    """Generate complete markdown documentation."""
    lines = []

    # Module docstring (contains title and intro sections)
    if module_docstring:
        lines.append(module_docstring.strip())
        lines.append("")

    # Extract sections from module docstring for TOC
    docstring_sections = (
        extract_sections_from_docstring(module_docstring) if module_docstring else []
    )

    # Table of Contents
    lines.extend(generate_toc(docstring_sections, models))

    # Configuration Reference
    lines.append("## Configuration Reference")
    lines.append("")

    for model in models:
        lines.append(f"### {model.__name__}")
        lines.append("")

        if model.__doc__:
            # Use cleandoc to strip common leading whitespace from docstrings
            lines.append(inspect.cleandoc(model.__doc__))
            lines.append("")

        table = generate_field_table(model)
        if table:
            lines.extend(table)
            lines.append("")

    # Full Examples section
    lines.append("## Complete Examples")
    lines.append("")
    lines.append("Auto-generated examples showing all fields with dummy values.")
    lines.append("")

    # Find root models (GlobalConfiguration and ProjectConfiguration)
    for model in models:
        if model.__name__ == "GlobalConfiguration":
            lines.extend(generate_full_example(model, "Global Configuration Example"))
        elif model.__name__ == "ProjectConfiguration":
            lines.extend(generate_full_example(model, "Project Configuration Example"))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate documentation from Pydantic models"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/yaml-configuration-guide.md")
    )
    parser.add_argument(
        "--check", action="store_true", help="Check if docs are up to date"
    )
    args = parser.parse_args()

    import hdlproject.models as models_package

    models = sort_by_dependencies(list(models_package.CONFIG_MODELS))
    content = generate_markdown(models_package.__doc__, models)

    print(f"Discovered {len(models)} models: {[m.__name__ for m in models]}")

    if args.check:
        if args.output.exists():
            if args.output.read_text() == content:
                print(f"Documentation is up to date: {args.output}")
                return 0
            print(f"Documentation is out of date: {args.output}")
            return 1
        print(f"Documentation file missing: {args.output}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content)
    print(f"Generated: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
