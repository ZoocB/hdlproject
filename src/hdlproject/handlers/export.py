# handlers/export.py
"""Export handler - refactored with service composition and step result patterns"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from hdlproject.handlers.base.handler import BaseHandler
from hdlproject.handlers.base.context import ExecutionContext, SingleProjectContext
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.registry import HandlerInfo, register_handler
from hdlproject.utils.vivado_output_parser import StepPattern
from hdlproject.utils.logging_manager import get_project_logger


@dataclass
class ExportOptions:
    """Export operation options"""

    clean: bool = False
    output_dir: Optional[str] = None


class ExportHandler(BaseHandler):
    """Handler for exporting Vivado projects"""

    CONFIG = OperationConfig(
        name="export",
        tcl_mode="export",
        step_patterns=[
            # Configuration loading
            StepPattern("Loading Configuration", [r"Loading configuration from"]),
            StepPattern("Setting up Project", [r"Setting up Project\.\.\."]),
            # HDLProject step result patterns
            StepPattern(
                "Processing IP Cores",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_xcis::process_xcis",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_xcis::process_xcis",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_xcis::process_xcis",
                ],
            ),
            StepPattern(
                "Loading HDL Sources",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_source_files::process_source_files",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_source_files::process_source_files",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_source_files::process_source_files",
                ],
            ),
            StepPattern(
                "Processing Block Designs",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_bds::process_bds",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_bds::process_bds",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_bds::process_bds",
                ],
            ),
            StepPattern(
                "Loading Constraints",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_constraints::process_constraints",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_constraints::process_constraints",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_constraints::process_constraints",
                ],
            ),
            StepPattern(
                "Setting Top Level",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_source_files::set_top_level",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_source_files::set_top_level",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_source_files::set_top_level",
                ],
            ),
            StepPattern(
                "Configuring Synthesis",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_synth_settings::configure_synth_settings",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_synth_settings::configure_synth_settings",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_synth_settings::configure_synth_settings",
                ],
            ),
            StepPattern(
                "Applying Synthesis Options",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_synth_settings::apply_custom_synth_options",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_synth_settings::apply_custom_synth_options",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_synth_settings::apply_custom_synth_options",
                ],
            ),
            StepPattern(
                "Applying Generics",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_synth_settings::apply_top_level_generics",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_synth_settings::apply_top_level_generics",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_synth_settings::apply_top_level_generics",
                ],
            ),
            StepPattern(
                "Configuring Implementation",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_impl_settings::configure_impl_settings",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_impl_settings::configure_impl_settings",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_impl_settings::configure_impl_settings",
                ],
            ),
            StepPattern(
                "Applying Implementation Options",
                [
                    r"\[HDLPROJECT_STEP_SUCCESS\] handle_impl_settings::apply_custom_impl_options",
                    r"\[HDLPROJECT_STEP_WARNING\] handle_impl_settings::apply_custom_impl_options",
                    r"\[HDLPROJECT_STEP_ERROR\] handle_impl_settings::apply_custom_impl_options",
                ],
            ),
            # Export-specific steps
            StepPattern(
                "Archiving Project", [r"archive_project", r"archiving project"]
            ),
            StepPattern(
                "Creating Archive", [r"creating tar\.gz", r"Project exported to"]
            ),
            StepPattern("Writing Manifest", [r"manifest\.json", r"writing manifest"]),
        ],
        operation_steps=[
            "Loading Configuration",
            "Setting up Project",
            "Processing IP Cores",
            "Loading HDL Sources",
            "Processing Block Designs",
            "Loading Constraints",
            "Setting Top Level",
            "Configuring Synthesis",
            "Applying Synthesis Options",
            "Applying Generics",
            "Configuring Implementation",
            "Applying Implementation Options",
            "Archiving Project",
            "Creating Archive",
            "Writing Manifest",
        ],
    )

    def configure(self, context: ExecutionContext) -> None:
        """Display export configuration"""
        print("\n" + "=" * 50)
        print("Export Configuration")
        print("=" * 50)
        print(f"Projects: {len(context.projects)}")
        print(f"Clean export: {'Yes' if context.options.clean else 'No'}")
        if context.options.output_dir:
            print(f"Output directory: {context.options.output_dir}")
        print("\nProjects to export:")
        for proj_ctx in context.projects:
            print(f"  - {proj_ctx.config.name}")
        print("=" * 50 + "\n")

    def prepare(self, context: SingleProjectContext) -> None:
        """Prepare for export - generate compile order"""
        project_logger = get_project_logger(context.project.config.name)

        # Handle custom output directory
        if context.options.output_dir:
            custom_output = Path(context.options.output_dir)
            custom_output.mkdir(parents=True, exist_ok=True)
            project_logger.info(f"Using custom output directory: {custom_output}")

        # Generate compile order if available
        if context.compile_order_service.is_available():
            compile_order_path = context.compile_order_service.generate_for_project(
                context.project
            )
            context.project.compile_order_path = compile_order_path
        else:
            project_logger.debug("Compile order service not available")

    def execute_single(self, context: SingleProjectContext) -> bool:
        """Execute export operation"""
        project_logger = get_project_logger(context.project.config.name)
        project_logger.info("Starting export")

        result = context.vivado_executor.execute(
            project_context=context.project,
            tcl_mode=self.CONFIG.tcl_mode,
            step_patterns=self.CONFIG.step_patterns,
            status_display=context.status_manager.display,
        )

        if not result.success:
            project_logger.error("Export failed - check log for details")

        return result.success


# Register handler
register_handler(
    HandlerInfo(
        name="export",
        handler_class=ExportHandler,
        options_class=ExportOptions,
        description="Export Vivado projects to archive",
        menu_name="Export Project",
        cli_arguments=[
            {"name": "projects", "nargs": "+", "help": "Project names to export"},
            {
                "name": "--output-dir",
                "type": str,
                "default": None,
                "help": "Custom output directory",
            },
            {
                "name": "--clean",
                "action": "store_true",
                "help": "Clean export directories",
            },
        ],
        supports_multiple=True,
    )
)
