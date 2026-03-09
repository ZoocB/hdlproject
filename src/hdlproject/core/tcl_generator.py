"""Generates TCL scripts from Jinja2 templates for Vivado project management.

Renders parameterized TCL based on the resolved project configuration.
Generated scripts are written to the operation directory alongside the
config JSON, making them inspectable and debuggable.

Flow:
    ResolvedProjectConfig → Jinja2 templates → generated .tcl in operation dir
    Static handler TCL (handle_*.tcl, common.tcl, config.tcl) copied alongside.

    BuildConfiguration.build_variables → resolved → available in templates
    BuildConfiguration.generated_sources → rendered → added to Vivado project
"""

import shutil
from pathlib import Path
from typing import Union

from jinja2 import Environment, FileSystemLoader, PackageLoader, Template

from hdlproject.core.build_variable_resolver import BuildVariableResolver
from hdlproject.models.resolved import ResolvedProjectConfig, ResolvedOperationPaths
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)

# Static TCL files that are copied as-is (handler logic, not templated)
STATIC_TCL_FILES = [
    "common.tcl",
    "config.tcl",
    "build.tcl",
    "handle_source_files.tcl",
    "handle_constraints.tcl",
    "handle_bds.tcl",
    "handle_xcis.tcl",
    "handle_synth_settings.tcl",
    "handle_impl_settings.tcl",
]


class TclGenerator:
    """Renders TCL scripts from Jinja2 templates for Vivado workflows.

    Static handler TCL files (handle_*.tcl, common.tcl, config.tcl) are
    copied unchanged. The orchestration scripts (project_workflow, build,
    export, open) are rendered from Jinja2 templates with project-specific
    configuration baked in.

    Also handles:
    - Resolving build variables (static values and shell commands)
    - Rendering user-provided generated source templates (e.g., VHDL packages)
    """

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("hdlproject", "tcl/vivado/templates"),
            keep_trailing_newline=True,
            lstrip_blocks=True,
            trim_blocks=True,
        )
        self._variable_resolver = BuildVariableResolver()

    def generate(
        self,
        resolved_config: ResolvedProjectConfig,
        operation_paths: ResolvedOperationPaths,
        mode: str,
        cores: int = 1,
        build_steps: list[str] | None = None,
    ) -> Path:
        """Render all TCL scripts to the operation directory.

        Args:
            resolved_config: Fully resolved project configuration
            operation_paths: Paths for this operation
            mode: Operation mode (build, open, export)
            cores: CPU cores for build
            build_steps: Build steps to run (default: all)

        Returns:
            Path to the generated entry-point TCL script
        """
        output_dir = operation_paths.operation_dir / "tcl"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Resolve build variables
        resolved_variables = self._resolve_build_variables(resolved_config)

        # Resolve artefact name template
        artefact_name = self._resolve_artefact_name(
            resolved_config, resolved_variables
        )

        # Render user-provided generated source templates
        generated_files = self._render_generated_sources(
            resolved_config, operation_paths, resolved_variables
        )

        # Copy static TCL files
        self._copy_static_scripts(output_dir)

        # Build template context from resolved config
        context = self._build_context(
            resolved_config, operation_paths, mode, cores,
            build_steps, resolved_variables, generated_files,
            artefact_name,
        )

        # Render the main workflow template
        self._render_template("project_workflow.tcl.j2", output_dir, context)

        entry_point = output_dir / "project_workflow.tcl"
        logger.debug(f"Generated TCL entry point: {entry_point}")
        return entry_point

    def _resolve_build_variables(
        self,
        config: ResolvedProjectConfig,
    ) -> dict[str, Union[str, int, float]]:
        """Resolve all build variables from the configuration.

        Args:
            config: Resolved project configuration

        Returns:
            Dict of variable name to resolved value
        """
        build_vars = config.build_configuration.build_variables
        if not build_vars:
            return {}

        working_dir = config.paths.project_dir
        resolved = self._variable_resolver.resolve_all(build_vars, working_dir)

        logger.info(f"Resolved {len(resolved)} build variable(s)")
        return resolved

    def _resolve_artefact_name(
        self,
        config: ResolvedProjectConfig,
        resolved_variables: dict[str, Union[str, int, float]],
    ) -> str | None:
        """Resolve the artefact name from a Jinja2 template string.

        Uses the same context as generated sources: full resolved config
        plus resolved build variables.

        Args:
            config: Resolved project configuration
            resolved_variables: Already-resolved build variables

        Returns:
            Rendered artefact name string, or None if not configured
        """
        template_str = config.build_configuration.artefact_name
        if not template_str:
            return None

        template_context = config.model_dump(mode="json", exclude_none=True)
        template_context["build_variables"] = resolved_variables

        template = Template(template_str)
        rendered = template.render(**template_context).strip()

        logger.info(f"Resolved artefact name: {rendered}")
        return rendered

    def _render_generated_sources(
        self,
        config: ResolvedProjectConfig,
        operation_paths: ResolvedOperationPaths,
        resolved_variables: dict[str, Union[str, int, float]],
    ) -> list[Path]:
        """Render user-provided generated source templates.

        Templates are Jinja2 files (e.g., VHDL packages) that have access to
        the full project configuration and resolved build variables.

        Args:
            config: Resolved project configuration
            operation_paths: Paths for this operation
            resolved_variables: Already-resolved build variables

        Returns:
            List of paths to generated files
        """
        generated_sources = config.build_configuration.generated_sources
        if not generated_sources:
            return []

        # Output directory for generated files
        gen_dir = operation_paths.operation_dir / "generated"
        gen_dir.mkdir(parents=True, exist_ok=True)

        # Build the template context — mirrors the YAML config structure
        # so users reference values explicitly (e.g., {{ project_information.project_name }})
        template_context = config.model_dump(mode="json", exclude_none=True)
        template_context["build_variables"] = resolved_variables

        generated_files = []
        project_dir = config.paths.project_dir

        for source in generated_sources:
            template_path = project_dir / source.template
            if not template_path.exists():
                raise FileNotFoundError(
                    f"Generated source template not found: {template_path}\n"
                    f"  Specified in build_configuration.generated_sources"
                )

            # Create a Jinja2 environment rooted at the template's directory
            template_dir = template_path.parent
            source_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                keep_trailing_newline=True,
            )

            template = source_env.get_template(template_path.name)
            rendered = template.render(**template_context)

            # Output filename: strip .j2 extension
            output_name = template_path.name.removesuffix(".j2")
            output_path = gen_dir / output_name
            output_path.write_text(rendered)

            generated_files.append(output_path)
            logger.info(f"Generated source: {source.template} -> {output_path}")

        return generated_files

    def _build_context(
        self,
        config: ResolvedProjectConfig,
        paths: ResolvedOperationPaths,
        mode: str,
        cores: int,
        build_steps: list[str] | None,
        resolved_variables: dict[str, Union[str, int, float]],
        generated_files: list[Path],
        artefact_name: str | None = None,
    ) -> dict:
        """Build the Jinja2 template context dict from resolved config."""
        proj_info = config.project_information
        device = proj_info.device_info

        if build_steps is None:
            build_steps = ["synthesis", "implementation", "bitstream"]

        hooks = config.hooks

        return {
            # Operation
            "mode": mode,
            "cores": cores,
            "build_steps": build_steps,
            # Project identity
            "project_name": config.vivado_project_name,
            "top_level": proj_info.top_level_file_name,
            "tool_version_year": proj_info.tool_version_year,
            # Device
            "part": device.part_name,
            "board_name": device.board_name or "",
            "board_part": device.board_part or "",
            # Paths
            "vivado_project_dir": str(paths.project_dir),
            "operation_dir": str(paths.operation_dir),
            "bd_dir": str(paths.bd_dir),
            "xci_dir": str(paths.xci_dir),
            "project_root": str(config.paths.project_dir),
            "config_file": str(config.paths.resolved_config_path),
            # Build configuration
            "build_configuration": config.build_configuration.model_dump(),
            # Build variables (resolved)
            "build_variables": resolved_variables,
            # Artifact naming
            "artefact_name": artefact_name,
            # Generated source files to add to project
            "generated_source_files": [str(f) for f in generated_files],
            # Hooks
            "hooks": hooks.model_dump(),
        }

    def _render_template(
        self,
        template_name: str,
        output_dir: Path,
        context: dict,
    ) -> Path:
        """Render a single Jinja2 template to the output directory.

        Args:
            template_name: Template filename (e.g. 'project_workflow.tcl.j2')
            output_dir: Directory to write the rendered script
            context: Jinja2 template context

        Returns:
            Path to the rendered file
        """
        template = self.env.get_template(template_name)
        rendered = template.render(**context)

        # Strip .j2 extension for output filename
        output_name = template_name.removesuffix(".j2")
        output_path = output_dir / output_name

        output_path.write_text(rendered)
        logger.debug(f"Rendered template: {template_name} -> {output_path}")
        return output_path

    def _copy_static_scripts(self, output_dir: Path) -> None:
        """Copy static TCL scripts to the output directory."""
        static_dir = Path(__file__).parent.parent / "tcl" / "vivado" / "static"

        if not static_dir.exists():
            raise FileNotFoundError(
                f"Static TCL directory not found: {static_dir}"
            )

        for filename in STATIC_TCL_FILES:
            src = static_dir / filename
            if not src.exists():
                logger.warning(f"Static TCL file not found: {src}")
                continue
            dst = output_dir / filename
            shutil.copy2(src, dst)

        logger.debug(f"Copied {len(STATIC_TCL_FILES)} static TCL files to {output_dir}")
