# handlers/open_project.py
"""Open project handler - refactored with service composition"""

from dataclasses import dataclass

from hdlproject.handlers.base.handler import BaseHandler
from hdlproject.handlers.base.context import ExecutionContext, SingleProjectContext
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.registry import HandlerInfo, register_handler
from hdlproject.utils.vivado_output_parser import StepPattern
from hdlproject.utils.logging_manager import get_project_logger


@dataclass
class OpenOptions:
    """Open operation options"""
    mode: str = 'edit'  # 'edit' or 'build'
    clean: bool = False


class OpenProjectHandler(BaseHandler):
    """Handler for opening projects"""
    
    CONFIG = OperationConfig(
        name="open",
        tcl_mode="open",
        step_patterns=[
            StepPattern("Loading Configuration", [r"Loading configuration from"]),
            StepPattern("Setting up Project", [r"Setting up Project\.\.\."]),
            StepPattern("Processing IP Cores", [r"handle_xcis::process_xcis success"]),
            StepPattern("Loading HDL Sources", [r"handle_source_files::process_source_files success"]),
            StepPattern("Processing Block Designs", [r"handle_bds::process_bds success"]),
            StepPattern("Loading Constraints", [r"handle_constraints::process_constraints success"]),
            StepPattern("Setting Top Level", [r"handle_source_files::set_top_level success"]),
            StepPattern("Configuring Synthesis", [r"handle_synth_settings::configure_synth_settings success"]),
            StepPattern("Configuring Implementation", [r"handle_impl_settings::configure_impl_settings success"]),
            StepPattern("Opening GUI", [r"Opening Vivado GUI"]),
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
            "Configuring Implementation",
            "Opening GUI"
        ],
        supports_gui=True
    )

    def configure(self, context: ExecutionContext) -> None:
        """Display open configuration"""
        print("\n" + "="*50)
        print("Open Configuration")
        print("="*50)
        print(f"Projects: {len(context.projects)}")
        print(f"Mode: {context.options.mode}")
        print(f"Clean: {'Yes' if context.options.clean else 'No'}")
        print("\nProjects to open:")
        for proj_ctx in context.projects:
            print(f"  - {proj_ctx.config.name}")
        print("="*50 + "\n")
    
    def prepare(self, context: SingleProjectContext) -> None:
        """Prepare for open operation"""
        project_logger = get_project_logger(context.project.config.name)
        
        if context.options.mode == 'edit':
            # Edit mode: generate compile order if available
            if context.compile_order_service.is_available():
                compile_order_path = context.compile_order_service.generate_for_project(
                    context.project
                )
                context.project.compile_order_path = compile_order_path
        
        elif context.options.mode == 'build':
            # Build mode: verify project exists
            xpr_path = self._find_project_file(
                context.project.config.name,
                ['build']
            )
            
            if not xpr_path:
                raise FileNotFoundError(
                    f"Build project not found for {context.project.config.name}. "
                    "Please build the project first."
                )
            
            # Store path for execution
            context.project.build_xpr_path = xpr_path
    
    def execute_single(self, context: SingleProjectContext) -> bool:
        """Execute open operation"""
        if context.options.mode == 'edit':
            return self._open_for_edit(context)
        else:
            return self._open_build_project(context)
    
    def _open_for_edit(self, context: SingleProjectContext) -> bool:
        """Open project for editing using TCL workflow"""
        result = context.vivado_executor.execute(
            project_context=context.project,
            tcl_mode=self.CONFIG.tcl_mode,
            step_patterns=self.CONFIG.step_patterns,
            status_display=context.status_manager.display
        )
        return result.success
    
    def _open_build_project(self, context: SingleProjectContext) -> bool:
        """Open existing build project directly in GUI"""
        project_logger = get_project_logger(context.project.config.name)
        
        if not hasattr(context.project, 'build_xpr_path'):
            project_logger.error("Build project path not found")
            return False
        
        # Update status
        context.status_manager.start_project(context.project.config.name)
        context.status_manager.update_step(context.project.config.name, "Opening GUI")
        
        # Open GUI
        success = context.vivado_executor.execute_gui(
            project_path=context.project.build_xpr_path,
            vivado_version=context.project.config.vivado_version
        )
        
        # Complete status
        context.status_manager.complete_project(
            context.project.config.name,
            success=success
        )
        
        return success


# Register handler
register_handler(HandlerInfo(
    name="open",
    handler_class=OpenProjectHandler,
    options_class=OpenOptions,
    description="Open Vivado projects",
    menu_name="Open Project",
    cli_arguments=[
        {"name": "projects", "nargs": "+", "help": "Project names to open"},
        {
            "name": "--mode",
            "choices": ["edit", "build"],
            "default": "edit",
            "help": "Open mode: edit (for editing) or build (open existing)"
        },
        {"name": "--clean", "action": "store_true", "help": "Clean directories (edit mode)"}
    ],
    supports_multiple=True
))