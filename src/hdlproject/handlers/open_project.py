"""Open project handler - opens Vivado projects for editing.

This handler opens Vivado in GUI mode with the project loaded.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hdlproject.handlers.base.handler import BaseHandler
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.registry import HandlerInfo, register_handler
from hdlproject.runtime.context import ExecutionContext, SingleProjectExecution
from hdlproject.utils.vivado_output_parser import StepPattern
from hdlproject.utils.logging_manager import get_project_logger


@dataclass
class OpenHandlerOptions:
    """Open operation options."""

    mode: str = "edit"  # 'edit' or 'build'
    clean: bool = False


class OpenProjectHandler(BaseHandler):
    """Handler for opening Vivado projects."""

    CONFIG = OperationConfig(
        name="open",
        tcl_mode="open",
        step_patterns=[
            # Start patterns for initial setup
            StepPattern.start("Loading Configuration", r"Loading configuration from"),
            StepPattern.start("Setting up Project", r"Setting up Project"),
            # TCL step patterns
            StepPattern.tcl("Processing IP Cores", "handle_xcis::process_xcis"),
            StepPattern.tcl(
                "Loading HDL Sources", "handle_source_files::process_source_files"
            ),
            StepPattern.tcl("Processing Block Designs", "handle_bds::process_bds"),
            StepPattern.tcl(
                "Loading Constraints", "handle_constraints::process_constraints"
            ),
            StepPattern.tcl("Setting Top Level", "handle_source_files::set_top_level"),
            StepPattern.tcl(
                "Configuring Synthesis",
                "handle_synth_settings::configure_synth_settings",
            ),
            StepPattern.tcl(
                "Applying Synthesis Options",
                "handle_synth_settings::apply_custom_synth_options",
            ),
            StepPattern.tcl(
                "Applying Generics", "handle_synth_settings::apply_top_level_generics"
            ),
            StepPattern.tcl(
                "Configuring Implementation",
                "handle_impl_settings::configure_impl_settings",
            ),
            StepPattern.tcl(
                "Applying Implementation Options",
                "handle_impl_settings::apply_custom_impl_options",
            ),
            # Opening GUI
            StepPattern.start("Opening GUI", r"Opening Vivado GUI"),
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
            "Opening GUI",
        ],
        supports_gui=True,
    )

    def configure(self, context: ExecutionContext) -> None:
        """Display open configuration."""
        print("\n" + "=" * 50)
        print("Open Configuration")
        print("=" * 50)
        print(f"Projects: {len(context.project_runtimes)}")
        print(f"Mode: {context.handler_options.mode}")
        print(f"Clean: {'Yes' if context.handler_options.clean else 'No'}")
        print("\nProjects to open:")
        for runtime in context.project_runtimes:
            print(f"  - {runtime.project_name}")
        print("=" * 50 + "\n")

    def prepare(self, context: SingleProjectExecution) -> None:
        """Prepare for open operation."""
        if context.handler_options.mode == "edit":
            # Edit mode: prepare compile order
            context.services.compile_order_service.prepare_for_operation(
                context.operation_paths
            )
        # Build mode: validation done in execute_single to avoid dynamic attributes

    def execute_single(self, context: SingleProjectExecution) -> bool:
        """Execute open operation."""
        if context.handler_options.mode == "edit":
            return self._open_for_edit(context)
        else:
            return self._open_build_project(context)

    def _open_for_edit(self, context: SingleProjectExecution) -> bool:
        """Open project for editing using TCL workflow."""
        extra_commands = context.services.compile_order_service.get_extra_commands(
            context.operation_paths
        )

        result = context.services.vivado_executor.execute(
            runtime=context.runtime,
            global_config=self.environment.global_config,
            operation_paths=context.operation_paths,
            tcl_mode=self.CONFIG.tcl_mode,
            step_patterns=self.CONFIG.step_patterns,
            status_display=context.services.status_manager.display,
            extra_commands=extra_commands,
        )
        return result.success

    def _open_build_project(self, context: SingleProjectExecution) -> bool:
        """Open existing build project directly in GUI."""
        project_logger = get_project_logger(context.project_name)

        # Find the build project
        xpr_path = self._find_build_project(context.runtime)
        if not xpr_path:
            project_logger.error(
                f"Build project not found for {context.project_name}. "
                "Please build the project first."
            )
            return False

        # Update status
        context.services.status_manager.start_project(context.project_name)
        context.services.status_manager.update_step(context.project_name, "Opening GUI")

        # Open GUI
        success = context.services.vivado_executor.execute_gui(
            runtime=context.runtime,
            global_config=self.environment.global_config,
            project_path=xpr_path,
        )

        # Complete status
        context.services.status_manager.complete_project(
            context.project_name,
            success=success,
        )

        return success

    def _find_build_project(self, runtime) -> Optional[Path]:
        """Find existing build project .xpr file."""
        # Check in build operation directory
        build_paths = runtime.get_operation_paths("build")
        # Use vivado_project_name - the .xpr is named after the YAML project name
        xpr_path = build_paths.get_project_file(runtime.vivado_project_name)

        if xpr_path.exists():
            return xpr_path

        return None


# Register handler
register_handler(
    HandlerInfo(
        name="open",
        handler_class=OpenProjectHandler,
        options_class=OpenHandlerOptions,
        description="Open Vivado projects",
        menu_name="Open Project",
        cli_arguments=[
            {"name": "projects", "nargs": "+", "help": "Project names to open"},
            {
                "name": "--mode",
                "choices": ["edit", "build"],
                "default": "edit",
                "help": "Open mode: edit (for editing) or build (open existing)",
            },
            {
                "name": "--clean",
                "action": "store_true",
                "help": "Clean directories (edit mode)",
            },
        ],
        supports_multiple=True,
    )
)
