# handlers/base/handler.py
"""Slim base handler using service composition"""

import shutil
from pathlib import Path
from typing import Any, Optional
from abc import ABC, abstractmethod

from hdlproject.handlers.base.context import (
    ExecutionContext, ProjectContext, SingleProjectContext
)
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.services.project_loader import ProjectLoader
from hdlproject.handlers.services.vivado_executor import VivadoExecutor
from hdlproject.handlers.services.status_manager import StatusManager
from hdlproject.handlers.services.compile_order_service import CompileOrderService
from hdlproject.core.compile_order import CompileOrderManager
from hdlproject.utils.logging_manager import (
    get_logger, get_project_logger, setup_project_log
)

logger = get_logger(__name__)


class BaseHandler(ABC):
    """
    Slim orchestration-only base handler.
    Services handle the actual work.
    
    Subclasses must:
    1. Define CONFIG class attribute (OperationConfig)
    2. Implement configure() - display configuration
    3. Implement prepare() - pre-execution setup
    4. Implement execute_single() - execute for one project
    """
    
    # Subclasses must define this
    CONFIG: OperationConfig
    
    def __init__(self, environment: dict[str, Any], interactive: bool = False):
        """
        Initialise handler with environment and mode.
        
        Args:
            environment: dict with project_dir, repository_root, vivado_location, etc.
            interactive: Whether running in interactive/menu mode
        """
        self.environment = environment
        self.interactive = interactive
        
        # Compose services
        self.project_loader = ProjectLoader(environment)
        self.vivado_executor = VivadoExecutor()
        self.compile_order_service = self._create_compile_order_service()
        
        # Status manager created per execution
        self.status_manager: Optional[StatusManager] = None
    
    def execute(self, projects: list[str], options: Any) -> None:
        """
        Main orchestration - loads projects and calls lifecycle hooks.
        
        Args:
            projects: list of project names to process
            options: Handler-specific options object
        """
        try:
            # 1. Load all projects
            logger.info(f"Loading {len(projects)} project(s)")
            project_contexts = self.project_loader.load_projects(
                projects, 
                self.CONFIG.name
            )
            
            # 2. Setup project logging
            for proj_ctx in project_contexts:
                log_path = proj_ctx.operation_paths.get_log_file(self.CONFIG.name)
                setup_project_log(proj_ctx.config.name, log_path)
            
            # 3. Create status manager
            self.status_manager = StatusManager(
                operation_name=self.CONFIG.name,
                operation_steps=self.CONFIG.operation_steps,
                project_names=projects
            )
            
            # 3b. Set log file paths for status display
            for proj_ctx in project_contexts:
                log_file = proj_ctx.operation_paths.get_log_file(self.CONFIG.name)
                self.status_manager.set_project_log_file(proj_ctx.config.name, log_file)
            
            # 3c. Start the display
            self.status_manager.start()
            
            # 4. Create execution context
            context = ExecutionContext(
                projects=project_contexts,
                options=options,
                operation_config=self.CONFIG,
                environment=self.environment,
                vivado_executor=self.vivado_executor,
                status_manager=self.status_manager,
                compile_order_service=self.compile_order_service
            )
            
            # 5. Display configuration (handler-specific)
            self.configure(context)
            
            # 6. Handle clean if requested
            if hasattr(options, 'clean') and options.clean:
                self._clean_operation_directories(context)
            
            # 7. Process each project
            results = {}
            for project_ctx in context.projects:
                single_ctx = self._make_single_context(context, project_ctx)
                
                try:
                    # Create operation directories
                    project_ctx.operation_paths.create_directories()
                    
                    # Resolve configuration for this operation
                    project_ctx.config.resolve_for_operation(
                        self.CONFIG.name,
                        project_ctx.operation_paths.operation_dir
                    )
                    
                    # Handler lifecycle hooks
                    self.prepare(single_ctx)
                    success = self.execute_single(single_ctx)
                    
                    results[project_ctx.config.name] = success
                    
                    if not success:
                        error_msg = f"Operation failed for {project_ctx.config.name}"
                        if not self.interactive:
                            raise RuntimeError(error_msg)
                        else:
                            logger.error(error_msg)
                    
                except Exception as e:
                    results[project_ctx.config.name] = False
                    logger.error(f"Project {project_ctx.config.name} failed: {e}", exc_info=True)
                    if not self.interactive:
                        raise
            
            # 8. Print summary with log locations
            self._print_operation_summary(context, results)
        
        finally:
            # Cleanup
            if self.status_manager:
                self.status_manager.cleanup()
    
    # === Hooks for subclasses ===
    
    @abstractmethod
    def configure(self, context: ExecutionContext) -> None:
        """
        Display configuration before execution.
        Called once with all projects.
        """
        pass
    
    @abstractmethod
    def prepare(self, context: SingleProjectContext) -> None:
        """
        Prepare single project before execution.
        Called for each project.
        """
        pass
    
    @abstractmethod
    def execute_single(self, context: SingleProjectContext) -> bool:
        """
        Execute operation for single project.
        Called for each project.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    # === Helper methods ===
    
    def get_project_list(self) -> list[str]:
        """Get list of available projects (directories with hdlproject_config.yaml)"""
        projects_dir = Path(self.environment['project_dir'])
        if not projects_dir.exists():
            return []
        
        projects = []
        for d in projects_dir.iterdir():
            if not d.is_dir() or d.name.startswith('.'):
                continue
            
            # Check for configuration file
            config_file = d / 'hdlproject_config.yaml'
            if config_file.exists():
                projects.append(d.name)
        
        return sorted(projects)
    
    def _create_compile_order_service(self) -> CompileOrderService:
        """Create compile order service if format specified"""
        compile_format = self.environment.get('compile_order_format')
        
        if compile_format:
            try:
                manager = CompileOrderManager(output_format=compile_format)
                logger.debug(f"Compile order service available: {compile_format}")
                return CompileOrderService(manager)
            except Exception as e:
                logger.warning(f"Could not create compile order manager: {e}")
        
        return CompileOrderService(None)
    
    def _make_single_context(self, exec_ctx: ExecutionContext, 
                            proj_ctx: ProjectContext) -> SingleProjectContext:
        """Create single project context from execution context"""
        return SingleProjectContext(
            project=proj_ctx,
            options=exec_ctx.options,
            operation_config=exec_ctx.operation_config,
            vivado_executor=exec_ctx.vivado_executor,
            status_manager=exec_ctx.status_manager,
            compile_order_service=exec_ctx.compile_order_service
        )
    
    def _clean_operation_directories(self, context: ExecutionContext) -> None:
        """Clean operation directories for all projects"""
        logger.info("Cleaning operation directories")
        
        for proj_ctx in context.projects:
            operation_dir = proj_ctx.operation_paths.operation_dir
            
            if operation_dir.exists():
                try:
                    shutil.rmtree(operation_dir)
                    logger.debug(f"Cleaned: {operation_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean {operation_dir}: {e}")
    
    def _find_project_file(self, project_name: str, 
                          search_operations: list[str]) -> Optional[Path]:
        """
        Find existing project file from previous operations.
        
        Args:
            project_name: Name of project
            search_operations: list of operations to search (e.g., ['build', 'open'])
            
        Returns:
            Path to .xpr file if found, None otherwise
        """
        project_loader = ProjectLoader(self.environment)
        
        for operation in search_operations:
            try:
                # Load with specific operation
                temp_ctx = project_loader.load_single_project(project_name, operation)
                xpr_path = temp_ctx.operation_paths.get_project_file(project_name)
                
                if xpr_path.exists():
                    logger.debug(f"Found project file: {xpr_path}")
                    return xpr_path
            except Exception:
                continue
        
        return None
    
    def _print_operation_summary(self, context: ExecutionContext, 
                                results: dict[str, bool]) -> None:
        """
        Print operation summary with log file locations.
        
        Args:
            context: Execution context
            results: dictionary of project_name -> success
        """
        if not self.interactive:
            return
        
        # Count successes and failures
        succeeded = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)
        
        # Print summary
        print("\n" + "="*60)
        print(f"{self.CONFIG.name.upper()} OPERATION SUMMARY")
        print("="*60)
        print(f"Total: {len(results)} project(s)")
        print(f"Succeeded: {succeeded}")
        print(f"Failed: {failed}")
        
        # Print log locations
        if failed > 0:
            print("\nLog files:")
            print(f"  Application log: {Path.cwd() / 'bin' / 'hdlproject.log'}")
            print(f"  Project logs:")
            for project_ctx in context.projects:
                log_file = project_ctx.operation_paths.get_log_file(self.CONFIG.name)
                status = "✓" if results.get(project_ctx.config.name, False) else "✗"
                print(f"    {status} {project_ctx.config.name}: {log_file}")
        
        print("="*60)