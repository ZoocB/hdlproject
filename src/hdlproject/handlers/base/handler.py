# handlers/base/handler.py
"""Slim base handler using service composition"""

import shutil
import psutil
from pathlib import Path
from typing import Any, Optional
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from hdlproject.handlers.base.context import (
    ExecutionContext,
    ProjectContext,
    SingleProjectContext,
)
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.services.project_loader import ProjectLoader
from hdlproject.handlers.services.vivado_executor import VivadoExecutor
from hdlproject.handlers.services.status_manager import StatusManager
from hdlproject.handlers.services.compile_order_service import CompileOrderService
from hdlproject.core.compile_order import CompileOrderManager
from hdlproject.utils.logging_manager import (
    get_logger,
    get_project_logger,
    setup_project_log,
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

        # Status manager created per execution
        self.status_manager: Optional[StatusManager] = None

    def execute(self, projects: list[str], options: Any) -> None:
        """
        Main orchestration - loads projects and calls lifecycle hooks.
        Supports parallel execution for handlers that enable it.

        Args:
            projects: list of project names to process
            options: Handler-specific options object
        """
        try:
            # 1. Load all projects
            logger.info(f"Loading {len(projects)} project(s)")
            project_contexts = self.project_loader.load_projects(
                projects, self.CONFIG.name
            )

            # 2. Setup project logging
            for proj_ctx in project_contexts:
                log_path = proj_ctx.operation_paths.get_log_file(self.CONFIG.name)
                setup_project_log(proj_ctx.config.name, log_path)

            # 3. Create status manager
            self.status_manager = StatusManager(
                operation_name=self.CONFIG.name,
                operation_steps=self.CONFIG.operation_steps,
                project_names=projects,
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
                compile_order_service=None,  # Created per-project
            )

            # 5. Display configuration (handler-specific)
            self.configure(context)

            # 6. Handle clean if requested
            if hasattr(options, "clean") and options.clean:
                self._clean_operation_directories(context)

            # 7. Determine if we should run in parallel
            supports_parallel = self._get_supports_parallel()
            should_parallelise = supports_parallel and len(project_contexts) > 1

            if should_parallelise:
                max_workers = self._calculate_max_workers(context)
                logger.info(
                    f"Running {len(project_contexts)} projects in parallel "
                    f"(max {max_workers} concurrent)"
                )
                results = self._execute_parallel(context, max_workers)
            else:
                if not supports_parallel and len(project_contexts) > 1:
                    logger.info(
                        f"Running {len(project_contexts)} projects sequentially "
                        "(parallel not supported)"
                    )
                results = self._execute_sequential(context)

            # 8. Print summary with log locations
            self._print_operation_summary(context, results)

        finally:
            # Cleanup
            if self.status_manager:
                self.status_manager.cleanup()

    def _execute_sequential(self, context: ExecutionContext) -> dict[str, bool]:
        """Execute projects sequentially."""
        results = {}

        for project_ctx in context.projects:
            compile_order_service = self._create_compile_order_service(project_ctx)
            single_ctx = self._make_single_context(
                context, project_ctx, compile_order_service
            )

            try:
                project_ctx.operation_paths.create_directories()
                project_ctx.config.resolve_for_operation(
                    self.CONFIG.name, project_ctx.operation_paths.operation_dir
                )

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
                logger.error(
                    f"Project {project_ctx.config.name} failed: {e}", exc_info=True
                )
                if not self.interactive:
                    raise

        return results

    def _execute_parallel(
        self, context: ExecutionContext, max_workers: int
    ) -> dict[str, bool]:
        """Execute projects in parallel using ThreadPoolExecutor."""
        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_project = {}

            for project_ctx in context.projects:
                future = executor.submit(
                    self._execute_single_project, context, project_ctx
                )
                future_to_project[future] = project_ctx.config.name

            for future in as_completed(future_to_project):
                project_name = future_to_project[future]

                try:
                    success = future.result()
                    results[project_name] = success

                    if not success:
                        error_msg = f"Operation failed for {project_name}"
                        if not self.interactive:
                            logger.error(error_msg)
                        else:
                            logger.error(error_msg)

                except Exception as e:
                    results[project_name] = False
                    logger.error(f"Project {project_name} failed: {e}", exc_info=True)
                    if not self.interactive:
                        logger.error(f"Will raise after all projects complete")

        if not self.interactive and any(not success for success in results.values()):
            failed_projects = [name for name, success in results.items() if not success]
            raise RuntimeError(
                f"Operation failed for {len(failed_projects)} project(s): {', '.join(failed_projects)}"
            )

        return results

    def _execute_single_project(
        self, context: ExecutionContext, project_ctx: ProjectContext
    ) -> bool:
        """Execute a single project (used by parallel executor)."""
        compile_order_service = self._create_compile_order_service(project_ctx)
        single_ctx = self._make_single_context(
            context, project_ctx, compile_order_service
        )

        try:
            project_ctx.operation_paths.create_directories()
            project_ctx.config.resolve_for_operation(
                self.CONFIG.name, project_ctx.operation_paths.operation_dir
            )

            self.prepare(single_ctx)
            success = self.execute_single(single_ctx)
            return success

        except Exception as e:
            logger.error(
                f"Project {project_ctx.config.name} failed: {e}", exc_info=True
            )
            return False

    def _calculate_max_workers(self, context: ExecutionContext) -> int:
        """Calculate maximum number of parallel workers based on system resources."""
        if hasattr(context.options, "cores") and context.options.cores:
            cores_per_project = context.options.cores
            total_cores = psutil.cpu_count(logical=True)
            max_workers = max(1, total_cores // cores_per_project)
            logger.debug(
                f"Core-based limit: {total_cores} system cores / "
                f"{cores_per_project} cores per project = {max_workers} max workers"
            )
            return min(max_workers, len(context.projects))
        else:
            default_max = 4
            max_workers = min(default_max, len(context.projects))
            logger.debug(
                f"Using default max workers: {max_workers} "
                f"(default: {default_max}, projects: {len(context.projects)})"
            )
            return max_workers

    def _get_supports_parallel(self) -> bool:
        """Check if this handler supports parallel execution."""
        from hdlproject.handlers.registry import get_handler

        handler_info = get_handler(self.CONFIG.name)
        if handler_info:
            return handler_info.supports_multiple

        logger.warning(
            f"Handler {self.CONFIG.name} not found in registry, "
            "defaulting to sequential execution"
        )
        return False

    # === Hooks for subclasses ===

    @abstractmethod
    def configure(self, context: ExecutionContext) -> None:
        """Display configuration before execution. Called once with all projects."""
        pass

    @abstractmethod
    def prepare(self, context: SingleProjectContext) -> None:
        """Prepare single project before execution. Called for each project."""
        pass

    @abstractmethod
    def execute_single(self, context: SingleProjectContext) -> bool:
        """Execute operation for single project. Returns True if successful."""
        pass

    # === Helper methods ===

    def get_project_list(self) -> list[str]:
        """Get list of available projects (directories with hdlproject_project_config.yaml)"""
        projects_dir = Path(self.environment["project_dir"])
        if not projects_dir.exists():
            return []

        projects = []
        for d in projects_dir.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue

            config_file = d / "hdlproject_project_config.yaml"
            if config_file.exists():
                projects.append(d.name)

        return sorted(projects)

    def _create_compile_order_service(
        self, project_ctx: ProjectContext
    ) -> CompileOrderService:
        """Create compile order service for a specific project."""
        compile_format = self.environment.get("compile_order_format")

        if not compile_format:
            logger.debug("No compile order format specified")
            return CompileOrderService(None)

        try:
            hdldepends_path = project_ctx.config.hdldepends_config_path
            manager = CompileOrderManager(
                output_format=compile_format, hdldepends_config_path=hdldepends_path
            )
            logger.debug(
                f"Compile order service created for {project_ctx.config.name} "
                f"using {hdldepends_path}"
            )
            return CompileOrderService(manager)

        except Exception as e:
            logger.warning(
                f"Could not create compile order manager for "
                f"{project_ctx.config.name}: {e}"
            )
            return CompileOrderService(None)

    def _make_single_context(
        self,
        exec_ctx: ExecutionContext,
        proj_ctx: ProjectContext,
        compile_order_service: CompileOrderService,
    ) -> SingleProjectContext:
        """Create single project context from execution context"""
        return SingleProjectContext(
            project=proj_ctx,
            options=exec_ctx.options,
            operation_config=exec_ctx.operation_config,
            vivado_executor=exec_ctx.vivado_executor,
            status_manager=exec_ctx.status_manager,
            compile_order_service=compile_order_service,
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

    def _find_project_file(
        self, project_name: str, search_operations: list[str]
    ) -> Optional[Path]:
        """Find existing project file from previous operations."""
        project_loader = ProjectLoader(self.environment)

        for operation in search_operations:
            try:
                temp_ctx = project_loader.load_single_project(project_name, operation)
                xpr_path = temp_ctx.operation_paths.get_project_file(project_name)

                if xpr_path.exists():
                    logger.debug(f"Found project file: {xpr_path}")
                    return xpr_path
            except Exception:
                continue

        return None

    def _print_operation_summary(
        self, context: ExecutionContext, results: dict[str, bool]
    ) -> None:
        """No-op - summary is handled by status_display."""
        pass
