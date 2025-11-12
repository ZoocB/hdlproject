# handlers/build.py
"""Build handler - refactored with service composition"""
from hdlproject.handlers.base.handler import BaseHandler
from hdlproject.handlers.base.context import ExecutionContext, SingleProjectContext
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.registry import HandlerInfo, register_handler
from hdlproject.utils.vivado_output_parser import StepPattern
from hdlproject.utils.logging_manager import get_project_logger
from dataclasses import dataclass


@dataclass
class BuildOptions:
    """Build operation options"""
    cores: int = 2
    clean: bool = False


class BuildHandler(BaseHandler):
    """Handler for building Vivado projects"""
    
    CONFIG = OperationConfig(
        name="build",
        tcl_mode="build",
        step_patterns=[
            StepPattern("Starting Synthesis", [r"launching runs -- synthesis"]),
            StepPattern("Synthesis Complete", [r"synth_design completed successfully"]),
            StepPattern("Starting Implementation", [r"launching runs -- implementation"]),
            StepPattern("Optimization Complete", [r"opt_design completed"]),
            StepPattern("Placement Complete", [r"place_design completed"]),
            StepPattern("Routing Complete", [r"route_design completed"]),
            StepPattern("Writing Bitstream", [r"write_bitstream completed successfully"]),
        ],
        operation_steps=[
            "Starting Synthesis",
            "Synthesis Complete",
            "Starting Implementation",
            "Optimization Complete",
            "Placement Complete",
            "Routing Complete",
            "Writing Bitstream"
        ]
    )
    
    def configure(self, context: ExecutionContext) -> None:
        """Display build configuration"""
        print("\n" + "="*50)
        print("Build Configuration")
        print("="*50)
        print(f"Projects: {len(context.projects)}")
        print(f"CPU cores per project: {context.options.cores}")
        print(f"Clean build: {'Yes' if context.options.clean else 'No'}")
        print("\nProjects to build:")
        for proj_ctx in context.projects:
            print(f"  - {proj_ctx.config.name}")
        print("="*50 + "\n")
    
    def prepare(self, context: SingleProjectContext) -> None:
        """Prepare for build - generate compile order"""
        project_logger = get_project_logger(context.project.config.name)
        
        if context.compile_order_service.is_available():
            compile_order_path = context.compile_order_service.generate_for_project(
                context.project
            )
            context.project.compile_order_path = compile_order_path
        else:
            project_logger.debug("Compile order service not available")
    
    def execute_single(self, context: SingleProjectContext) -> bool:
        """Execute build for single project"""
        project_logger = get_project_logger(context.project.config.name)
        project_logger.info(f"Building with {context.options.cores} cores")
        
        result = context.vivado_executor.execute(
            project_context=context.project,
            tcl_mode=self.CONFIG.tcl_mode,
            step_patterns=self.CONFIG.step_patterns,
            status_display=context.status_manager.display,
            cores=context.options.cores
        )
        
        if not result.success:
            project_logger.error("Build failed - check log for details")
        
        return result.success


register_handler(HandlerInfo(
    name="build",
    handler_class=BuildHandler,
    options_class=BuildOptions,
    description="Build Vivado projects from source",
    menu_name="Build Project",
    cli_arguments=[
        {"name": "projects", "nargs": "+", "help": "Project names to build"},
        {"name": "--cores", "type": int, "default": 2, "help": "CPU cores per project"},
        {"name": "--clean", "action": "store_true", "help": "Clean build directories"}
    ],
    supports_multiple=True
))

