"""Generates TCL scripts from Jinja2 templates for Vivado project management.

Renders parameterized TCL based on the resolved project configuration.
Generated scripts are written to the operation directory alongside the
config JSON, making them inspectable and debuggable.

Flow:
    ResolvedProjectConfig → Jinja2 templates → generated .tcl in operation dir
    Static handler TCL (handle_*.tcl, common.tcl, config.tcl) copied alongside.
"""

import shutil
from pathlib import Path

from jinja2 import Environment, PackageLoader

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
    """

    def __init__(self):
        self.env = Environment(
            loader=PackageLoader("hdlproject", "tcl/vivado/templates"),
            keep_trailing_newline=True,
            lstrip_blocks=True,
            trim_blocks=True,
        )

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

        # Copy static TCL files
        self._copy_static_scripts(output_dir)

        # Build template context from resolved config
        context = self._build_context(
            resolved_config, operation_paths, mode, cores, build_steps
        )

        # Render the main workflow template
        self._render_template("project_workflow.tcl.j2", output_dir, context)

        entry_point = output_dir / "project_workflow.tcl"
        logger.debug(f"Generated TCL entry point: {entry_point}")
        return entry_point

    def _build_context(
        self,
        config: ResolvedProjectConfig,
        paths: ResolvedOperationPaths,
        mode: str,
        cores: int,
        build_steps: list[str] | None,
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
        logger.debug(f"Rendered template: {template_name} → {output_path}")
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
