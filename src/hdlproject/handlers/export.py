# handlers/export.py
"""Export handler - refactored with service composition"""

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
            StepPattern("Creating Project", [r"creating project", r"opening project"]),
            StepPattern("Loading Design", [r"loading design", r"reading checkpoint"]),
            StepPattern("Archiving Project", [r"archiving project", r"archive_project"]),
            StepPattern("Creating Archive", [r"creating tar\.gz", r"creating archive"]),
            StepPattern("Writing Manifest", [r"writing manifest", r"manifest\.json"]),
            StepPattern("Export Complete", [r"project exported", r"export complete"]),
        ],
        operation_steps=[
            "Creating Project",
            "Loading Design",
            "Archiving Project",
            "Creating Archive",
            "Writing Manifest",
            "Export Complete"
        ]
    )
    
    def configure(self, context: ExecutionContext) -> None:
        """Display export configuration"""
        print("\n" + "="*50)
        print("Export Configuration")
        print("="*50)
        print(f"Projects: {len(context.projects)}")
        print(f"Clean export: {'Yes' if context.options.clean else 'No'}")
        if context.options.output_dir:
            print(f"Output directory: {context.options.output_dir}")
        print("\nProjects to export:")
        for proj_ctx in context.projects:
            print(f"  - {proj_ctx.config.name}")
        print("="*50 + "\n")
    
    def prepare(self, context: SingleProjectContext) -> None:
        """Prepare for export - verify project exists"""
        project_logger = get_project_logger(context.project.config.name)
        
        # Handle custom output directory
        if context.options.output_dir:
            custom_output = Path(context.options.output_dir)
            custom_output.mkdir(parents=True, exist_ok=True)
            project_logger.info(f"Using custom output directory: {custom_output}")
        
        # Verify project exists from build or open
        xpr_path = self._find_project_file(
            context.project.config.name,
            ['build', 'open']
        )
        
        if not xpr_path:
            raise FileNotFoundError(
                f"No project found to export for {context.project.config.name}. "
                "Please build or open the project first."
            )
    
    def execute_single(self, context: SingleProjectContext) -> bool:
        """Execute export operation"""
        project_logger = get_project_logger(context.project.config.name)
        project_logger.info("Starting export")
        
        result = context.vivado_executor.execute(
            project_context=context.project,
            tcl_mode=self.CONFIG.tcl_mode,
            step_patterns=self.CONFIG.step_patterns,
            status_display=context.status_manager.display
        )
        
        if not result.success:
            project_logger.error("Export failed - check log for details")
        
        return result.success


# Register handler
register_handler(HandlerInfo(
    name="export",
    handler_class=ExportHandler,
    options_class=ExportOptions,
    description="Export Vivado projects to archive",
    menu_name="Export Project",
    cli_arguments=[
        {"name": "projects", "nargs": "+", "help": "Project names to export"},
        {"name": "--output-dir", "type": str, "default": None, "help": "Custom output directory"},
        {"name": "--clean", "action": "store_true", "help": "Clean export directories"}
    ],
    supports_multiple=True
))