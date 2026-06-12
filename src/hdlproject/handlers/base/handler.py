"""base handler using service composition.

This module provides the base class for all operation handlers (build, export, etc.).
"""

import shutil
import signal
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import Any, Optional

import psutil

from hdlproject.config.loader import ConfigLoader
from hdlproject.core.cancellation import CancellationToken
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.services.compile_order_service import CompileOrderService
from hdlproject.handlers.services.project_loader import ProjectLoaderService
from hdlproject.handlers.services.status_manager import StatusManager
from hdlproject.handlers.services.tool_executor import ToolExecutorService
from hdlproject.models.resolved import ResolvedProjectConfig
from hdlproject.runtime.context import (
    ExecutionContext,
    ExecutionServices,
    RuntimeEnvironment,
    SingleProjectExecution,
)
from hdlproject.utils.logging_manager import (
    get_logger,
    setup_project_log,
)

logger = get_logger(__name__)


@contextmanager
def sigint_cancels(cancel_token: CancellationToken):
    """Make Ctrl+C request cooperative cancellation instead of raising.

    Only installs a handler when running on the main thread (signal handlers
    cannot be set elsewhere). In a worker thread — e.g. the Textual UI's build
    worker — this is a no-op and the front-end trips the token directly. The
    previous handler is always restored on exit.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def _handler(signum, frame):
        logger.warning("Interrupt received - cancelling (press Ctrl+C again to abort)")
        cancel_token.cancel()

    previous = signal.signal(signal.SIGINT, _handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)


@contextmanager
def execution_lifecycle(status_manager: StatusManager):
    """Context manager for execution lifecycle.

    Ensures status manager is properly cleaned up even if execution fails.

    Args:
        status_manager: StatusManager instance to manage

    Yields:
        The status manager for use during execution
    """
    try:
        status_manager.start()
        yield status_manager
    finally:
        status_manager.cleanup()


class BaseHandler(ABC):
    """Slim orchestration-only base handler.

    Services handle the actual work. Subclasses must:
    1. Define CONFIG class attribute (OperationConfig)
    2. Implement configure() - display configuration
    3. Implement prepare() - pre-execution setup
    4. Implement execute_single() - execute for one project
    """

    # Subclasses must define this
    CONFIG: OperationConfig

    def __init__(
        self,
        environment: RuntimeEnvironment,
        interactive: bool = False,
    ):
        """initialise handler with runtime environment.

        Args:
            environment: Runtime environment with global config
            interactive: Whether running in interactive/menu mode
        """
        self.environment = environment
        self.interactive = interactive

        # Create services
        self.config_loader = ConfigLoader(environment.repository_root)
        self.project_loader = ProjectLoaderService(
            self.config_loader,
            environment.global_config,
        )
        self.tool_executor_service = ToolExecutorService()

        # Status manager created per execution
        self.status_manager: Optional[StatusManager] = None

        # Cancellation token, shared with the executor. A front-end (e.g. the
        # Textual UI) may replace this before calling execute() so its cancel
        # binding can trip the same token.
        self.cancel_token = CancellationToken()

    def execute(self, projects: list[str], options: Any) -> None:
        """Main orchestration - loads projects and calls lifecycle hooks.

        Supports parallel execution for handlers that enable it. Ctrl+C during a
        run trips ``self.cancel_token`` (see ``sigint_cancels``), which the
        executor watches to terminate Vivado.

        Args:
            projects: List of project names to process
            options: Handler-specific options object (BuildHandlerOptions, etc.)
        """
        # 1. Load all resolved project configurations
        logger.info(f"Loading {len(projects)} project(s)")
        resolved_configs = self.project_loader.load_projects(
            projects,
            check_files=True,
        )

        # 2. Setup project logging
        for config in resolved_configs:
            operation_paths = config.get_operation_paths(self.CONFIG.name)
            operation_paths.create_directories()
            log_path = operation_paths.get_log_file(self.CONFIG.name)
            setup_project_log(config.project_name, log_path)

        # 3. Create status manager
        self.status_manager = StatusManager(
            operation_name=self.CONFIG.name,
            operation_steps=self.CONFIG.operation_steps,
            project_names=projects,
        )

        # 3b. Set log file paths for status display
        for config in resolved_configs:
            operation_paths = config.get_operation_paths(self.CONFIG.name)
            log_file = operation_paths.get_log_file(self.CONFIG.name)
            self.status_manager.set_project_log_file(config.project_name, log_file)

        # Use context managers for lifecycle + cancellation handling
        with sigint_cancels(self.cancel_token), execution_lifecycle(
            self.status_manager
        ):
            # 4. Create execution services
            services = ExecutionServices(
                tool_executor=self.tool_executor_service,
                status_manager=self.status_manager,
                compile_order_service=None,  # Created per-project
                cancel_token=self.cancel_token,
            )

            # 5. Create execution context
            context = ExecutionContext(
                environment=self.environment,
                resolved_configs=resolved_configs,
                handler_options=options,
                operation_config=self.CONFIG,
                services=services,
            )

            # 6. Display configuration (handler-specific)
            self.configure(context)

            # 7. Handle clean if requested
            if hasattr(options, "clean") and options.clean:
                self._clean_operation_directories(context)

            # 8. Run the projects (one thread pool, sized 1..N), then summarise.
            max_workers = self._resolve_worker_count(context)
            logger.info(
                f"Running {len(resolved_configs)} project(s) with up to "
                f"{max_workers} concurrent"
            )
            results = self._run_projects(context, max_workers)

            # 9. Print summary
            self._print_operation_summary(context, results)

    def _resolve_worker_count(self, context: ExecutionContext) -> int:
        """How many projects may run at once.

        One unless the handler opts into parallelism *and* there is more than one
        project, in which case it is bounded by CPU/config limits.
        """
        if not self.CONFIG.supports_parallel or len(context.resolved_configs) <= 1:
            return 1
        return self._calculate_max_workers(context)

    def _run_projects(
        self, context: ExecutionContext, max_workers: int
    ) -> dict[str, bool]:
        """Execute every project through one thread pool (1 worker == sequential).

        All projects run regardless of individual failures; in non-interactive
        mode a RuntimeError is raised at the end if any failed, so the batch exit
        code is non-zero while still reporting every result.
        """
        results: dict[str, bool] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_project = {
                executor.submit(self._execute_single_project, context, config):
                    config.project_name
                for config in context.resolved_configs
            }
            for future in as_completed(future_to_project):
                project_name = future_to_project[future]
                try:
                    results[project_name] = future.result()
                except Exception as e:
                    results[project_name] = False
                    logger.error(f"Project {project_name} failed: {e}", exc_info=True)
                if not results[project_name]:
                    logger.error(f"Operation failed for {project_name}")

        if not self.interactive and any(not ok for ok in results.values()):
            failed = [n for n, ok in results.items() if not ok]
            raise RuntimeError(
                f"Operation failed for {len(failed)} project(s): {', '.join(failed)}"
            )

        return results

    def _execute_single_project(
        self,
        context: ExecutionContext,
        config: ResolvedProjectConfig,
    ) -> bool:
        """Prepare and execute one project (the unit of work for the pool)."""
        # A queued worker that hasn't started yet should not launch Vivado once
        # cancellation has been requested.
        if self.cancel_token.cancelled:
            logger.warning(f"Cancelled - skipping {config.project_name}")
            return False

        single_ctx = self._create_single_execution(context, config)

        try:
            self.prepare(single_ctx)
            return self.execute_single(single_ctx)

        except Exception as e:
            logger.error(
                f"Project {config.project_name} failed: {e}",
                exc_info=True,
            )
            return False

    def _create_single_execution(
        self,
        context: ExecutionContext,
        config: ResolvedProjectConfig,
    ) -> SingleProjectExecution:
        """Create a SingleProjectExecution context."""
        # Get operation paths
        operation_paths = config.get_operation_paths(self.CONFIG.name)
        operation_paths.create_directories()

        # Export resolved config to disk
        config.export_to_disk(operation_paths.operation_dir)

        # Create compile order service for this project
        compile_order_service = self._create_compile_order_service(config)

        # Create services with project-specific compile order service
        services = ExecutionServices(
            tool_executor=context.services.tool_executor,
            status_manager=context.services.status_manager,
            compile_order_service=compile_order_service,
            cancel_token=context.services.cancel_token,
        )

        return SingleProjectExecution(
            resolved_config=config,
            operation_paths=operation_paths,
            handler_options=context.handler_options,
            operation_config=context.operation_config,
            services=services,
        )

    def _create_compile_order_service(
        self,
        config: ResolvedProjectConfig,
    ) -> CompileOrderService:
        """Create compile order service for a specific project."""
        compile_format = config.compile_order_format

        if not compile_format:
            logger.debug("No compile order format specified")
            return CompileOrderService(None, None)

        try:
            hdldepends_path = config.paths.hdldepends_config_path
            if hdldepends_path:
                from hdlproject.core.compile_order import CompileOrderManager

                manager = CompileOrderManager(
                    output_format=compile_format,
                    hdldepends_config_path=hdldepends_path,
                )
                return CompileOrderService(manager, config)
            else:
                return CompileOrderService(None, None)

        except Exception as e:
            logger.warning(
                f"Could not create compile order manager for "
                f"{config.project_name}: {e}"
            )
            return CompileOrderService(None, None)

    def _calculate_max_workers(self, context: ExecutionContext) -> int:
        """Calculate maximum number of parallel workers."""
        if hasattr(context.handler_options, "cores") and context.handler_options.cores:
            cores_per_project = context.handler_options.cores
            total_cores = psutil.cpu_count(logical=True)
            max_workers = max(1, total_cores // cores_per_project)
            return min(max_workers, len(context.resolved_configs))
        else:
            default_max = self.environment.global_config.max_parallel_builds or 4
            return min(default_max, len(context.resolved_configs))

    def _clean_operation_directories(self, context: ExecutionContext) -> None:
        """Clean operation directories for all projects."""
        logger.info("Cleaning operation directories")

        for config in context.resolved_configs:
            operation_paths = config.get_operation_paths(self.CONFIG.name)
            operation_dir = operation_paths.operation_dir

            if operation_dir.exists():
                try:
                    shutil.rmtree(operation_dir)
                    logger.debug(f"Cleaned: {operation_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean {operation_dir}: {e}")

    def _print_operation_summary(
        self,
        context: ExecutionContext,
        results: dict[str, bool],
    ) -> None:
        """Print operation summary. Override in subclasses if needed."""
        pass

    # === Abstract methods for subclasses ===

    @abstractmethod
    def configure(self, context: ExecutionContext) -> None:
        """Display configuration before execution.

        Called once with all projects.
        """
        pass

    @abstractmethod
    def prepare(self, context: SingleProjectExecution) -> None:
        """Prepare single project before execution.

        Called for each project before execute_single().
        """
        pass

    @abstractmethod
    def execute_single(self, context: SingleProjectExecution) -> bool:
        """Execute operation for single project.

        Returns:
            True if successful, False otherwise
        """
        pass
