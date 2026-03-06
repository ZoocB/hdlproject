"""Build handler - builds Vivado projects from source.

This handler executes the full build flow: synthesis, implementation,
and bitstream generation.
"""

from dataclasses import dataclass

from hdlproject.handlers.base.handler import BaseHandler
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.registry import HandlerInfo, register_handler
from hdlproject.runtime.context import ExecutionContext, SingleProjectExecution
from hdlproject.utils.vivado_output_parser import StepPattern
from hdlproject.utils.logging_manager import get_project_logger


@dataclass
class BuildHandlerOptions:
    """Build operation options.

    These are runtime options passed from the CLI, distinct from
    BuildConfiguration in the project config.
    """

    cores: int = 2
    clean: bool = False


class BuildHandler(BaseHandler):
    """Handler for building Vivado projects."""

    CONFIG = OperationConfig(
        name="build",
        tcl_mode="build",
        step_patterns=[
            # TCL step patterns - auto-expand to SUCCESS/WARNING/ERROR
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
            # Vivado build phases - start markers
            StepPattern.start("Synthesis", r"Launching Runs -- Synthesis"),
            StepPattern.start("Optimization", r"Command: opt_design"),
            StepPattern.start("Placement", r"Command: place_design"),
            StepPattern.start("Routing", r"Command: route_design"),
            StepPattern.start("Writing Bitstream", r"Command: write_bitstream"),
            # Vivado build phases - completion markers
            StepPattern.complete("Synthesis", r"synth_design completed"),
            StepPattern.complete("Optimization", r"opt_design completed"),
            StepPattern.complete("Placement", r"place_design completed"),
            StepPattern.complete("Routing", r"route_design completed"),
            StepPattern.complete("Writing Bitstream", r"write_bitstream completed"),
            # Vivado build phases - failure markers
            StepPattern.failed("Synthesis", r"synth_design failed"),
            StepPattern.failed("Optimization", r"opt_design failed"),
            StepPattern.failed("Placement", r"place_design failed"),
            StepPattern.failed("Routing", r"route_design failed"),
            StepPattern.failed("Writing Bitstream", r"write_bitstream failed"),
        ],
        operation_steps=[
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
            "Synthesis",
            "Optimization",
            "Placement",
            "Routing",
            "Writing Bitstream",
        ],
    )

    def configure(self, context: ExecutionContext) -> None:
        """Display build configuration."""
        print("\n" + "=" * 50)
        print("Build Configuration")
        print("=" * 50)
        print(f"Projects: {len(context.resolved_configs)}")
        print(f"CPU cores per project: {context.handler_options.cores}")
        print(f"Clean build: {'Yes' if context.handler_options.clean else 'No'}")
        print("\nProjects to build:")
        for config in context.resolved_configs:
            print(f"  - {config.project_name} ({config.tool} {config.tool_version})")
        print("=" * 50 + "\n")

    def prepare(self, context: SingleProjectExecution) -> None:
        """Prepare for build - generate compile order if local setup."""
        context.services.compile_order_service.prepare_for_operation(
            context.operation_paths
        )

    def execute_single(self, context: SingleProjectExecution) -> bool:
        """Execute build for single project."""
        project_logger = get_project_logger(context.project_name)
        project_logger.info(f"Building with {context.handler_options.cores} cores")

        extra_commands = context.services.compile_order_service.get_extra_commands(
            context.operation_paths
        )

        result = context.services.vivado_executor.execute(
            resolved_config=context.resolved_config,
            operation_paths=context.operation_paths,
            tcl_mode=self.CONFIG.tcl_mode,
            step_patterns=self.CONFIG.step_patterns,
            status_display=context.services.status_manager.display,
            cores=context.handler_options.cores,
            extra_commands=extra_commands,
        )

        if not result.success:
            project_logger.error("Build failed - check log for details")

        return result.success


# Register handler
register_handler(
    HandlerInfo(
        name="build",
        handler_class=BuildHandler,
        options_class=BuildHandlerOptions,
        description="Build Vivado projects from source",
        menu_name="Build Project",
        cli_arguments=[
            {"name": "projects", "nargs": "+", "help": "Project names to build"},
            {
                "name": "--cores",
                "type": int,
                "default": 2,
                "help": "CPU cores per project",
            },
            {
                "name": "--clean",
                "action": "store_true",
                "help": "Clean build directories",
            },
        ],
        supports_multiple=True,
    )
)
