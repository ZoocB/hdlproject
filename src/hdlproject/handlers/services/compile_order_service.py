# handlers/services/compile_order_service.py
"""Service for compile order generation"""

from pathlib import Path
from typing import Optional

from hdlproject.core.compile_order import CompileOrderManager
from hdlproject.handlers.base.context import ProjectContext
from hdlproject.utils.logging_manager import get_logger, get_project_logger

logger = get_logger(__name__)


class CompileOrderService:
    """Handles compile order generation for operations that need it"""
    
    def __init__(self, compile_manager: Optional[CompileOrderManager]):
        """
        Initialise service.
        
        Args:
            compile_manager: CompileOrderManager instance or None if not available
        """
        self.manager = compile_manager
    
    def generate_for_project(self, project_context: ProjectContext) -> Optional[Path]:
        """
        Generate compile order for a project if manager is available.
        
        Args:
            project_context: Project context with config and paths
            
        Returns:
            Path to generated compile order file, or None if not generated
        """
        if not self.is_available():
            logger.debug("Compile order generation not available")
            return None
        
        project_logger = get_project_logger(project_context.config.name)
        
        try:
            # Generate compile order
            compile_order_path = self.manager.generate(
                root_dir=project_context.config.repository_root,
                top_level_file=str(project_context.config.top_level_file_path),
                working_dir=project_context.operation_paths.operation_dir
            )
            
            if compile_order_path:
                project_logger.info(f"Generated compile order: {compile_order_path}")
                return compile_order_path
            else:
                project_logger.info("Compile order not generated (no hdldepends config)")
                return None
                
        except Exception as e:
            project_logger.warning(f"Compile order generation failed: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if compile order generation is available"""
        return self.manager is not None