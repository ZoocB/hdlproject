# core/application.py
"""Application container with internal initialisation"""

import subprocess
import shutil
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hdlproject.handlers.base.handler import BaseHandler

from hdlproject.config.loader import ConfigLoader
from hdlproject.runtime.context import RuntimeEnvironment
from hdlproject.constants import GLOBAL_CONFIG_FILENAME, PROJECT_CONFIG_FILENAME
from hdlproject.utils.logging_manager import (
    setup_application_log,
    set_verbosity,
    LogLevel,
    get_logger,
    cleanup,
)
from hdlproject.handlers.registry import load_all_handlers

logger = get_logger(__name__)


class Application:
    """
    Application container that manages:
    - Environment validation
    - Configuration resolution
    - Handler execution
    """

    def __init__(
        self,
        git_root: Path,
        project_dir: Path,
        compile_order_format: str,
        verbosity: LogLevel,
        vivado_location: Optional[Path] = None,
    ):
        """
        Initialise application with resolved configuration.

        Args:
            git_root: Git repository root
            project_dir: Projects base directory
            compile_order_format: Compile order output format
            verbosity: Logging verbosity level
            vivado_location: Optional Vivado installation path (for validation)
        """
        # Set verbosity first
        set_verbosity(verbosity)

        # Setup application log
        log_dir = git_root / "bin"
        self.app_log_path = setup_application_log(log_dir)

        # Store configuration
        self.git_root = git_root
        self.project_dir = project_dir
        self.compile_order_format = compile_order_format

        # Create RuntimeEnvironment (replaces legacy dict)
        self.runtime_environment = self._create_runtime_environment(
            git_root=git_root,
            vivado_location=vivado_location,
        )

        # Load all handlers
        load_all_handlers()

        logger.info("Application Initialised")
        logger.info(f"Git root: {git_root}")
        logger.info(f"Project dir: {project_dir}")
        logger.info(f"Compile order format: {compile_order_format}")

    def _create_runtime_environment(
        self,
        git_root: Path,
        vivado_location: Optional[Path] = None,
    ) -> RuntimeEnvironment:
        """
        Create the RuntimeEnvironment for handlers.

        Args:
            git_root: Git repository root
            vivado_location: Optional Vivado installation path

        Returns:
            RuntimeEnvironment with global config loaded
        """
        # Load global configuration
        config_loader = ConfigLoader(git_root)
        global_config = config_loader.load_global_config()

        return RuntimeEnvironment(
            repository_root=git_root,
            global_config=global_config,
            vivado_location=vivado_location,
        )

    @classmethod
    def from_args(cls, args) -> "Application":
        """
        Create application from CLI arguments.
        Handles all prerequisite validation and configuration resolution.

        Args:
            args: Parsed command line arguments

        Returns:
            Initialised Application instance

        Raises:
            RuntimeError: If prerequisites fail or configuration cannot be resolved
        """
        # Step 1: Validate prerequisites
        cls._validate_prerequisites()

        # Step 2: Discover git root
        git_root = cls._discover_git_root()
        logger.debug(f"Git root: {git_root}")

        # Step 3: Resolve project directory (CLI -> Config)
        project_dir = cls._resolve_project_dir(args, git_root)
        logger.info(f"Using project directory: {project_dir}")

        # Step 4: Resolve compile order format (CLI -> Config -> Default)
        repo_config = ConfigLoader(git_root).load_global_config()
        compile_format = (
            getattr(args, "compile_order_format", None)
            or repo_config.compile_order_format
            or "json"
        )

        # Step 5: Map verbosity from args
        verbosity = cls._map_verbosity(args)

        # Step 6: Get Vivado location if specified
        vivado_location = getattr(args, "vivado_location", None)
        if vivado_location:
            vivado_location = Path(vivado_location)

        # Create instance
        return cls(
            git_root=git_root,
            project_dir=project_dir,
            compile_order_format=compile_format,
            verbosity=verbosity,
            vivado_location=vivado_location,
        )

    @staticmethod
    def _validate_prerequisites() -> None:
        """
        Validate all prerequisites for running hdlproject.

        Raises:
            RuntimeError: If any prerequisite is not met
        """
        # Check for git
        if not shutil.which("git"):
            raise RuntimeError("git command not found in PATH")

        # Check for hdldepends
        if not shutil.which("hdldepends"):
            raise RuntimeError(
                "hdldepends command not found in PATH.\n"
                "Please install hdldepends:\n"
                "  pip install hdldepends"
            )

        logger.debug("Prerequisites validated")

    @staticmethod
    def _discover_git_root() -> Path:
        """
        Discover git repository root.

        Returns:
            Path to git repository root

        Raises:
            RuntimeError: If not in a git repository
        """
        try:
            # Add current directory as safe
            subprocess.run(
                [
                    "git",
                    "config",
                    "--global",
                    "--add",
                    "safe.directory",
                    str(Path.cwd()),
                ],
                check=False,
                capture_output=True,
            )

            # Get git root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(result.stdout.strip())

        except subprocess.CalledProcessError:
            raise RuntimeError(
                "Not in a git repository. hdlproject must be run from within a git repository."
            )

    @staticmethod
    def _resolve_project_dir(args, git_root: Path) -> Path:
        """
        Resolve project directory: CLI argument -> Config file.
        No default fallback - must be explicitly specified.

        Args:
            args: Parsed CLI arguments
            git_root: Git repository root

        Returns:
            Resolved project directory path

        Raises:
            RuntimeError: If project_dir cannot be resolved
        """
        # Load repository config
        repo_config = ConfigLoader(git_root).load_global_config()

        # Priority 1: CLI argument
        if hasattr(args, "project_dir") and args.project_dir:
            prj_dir = Path(args.project_dir)
            if not prj_dir.is_absolute():
                prj_dir = git_root / prj_dir
            logger.debug(f"Project dir from CLI: {prj_dir}")
            return prj_dir

        # Priority 2: Config file
        if repo_config.project_dir:
            prj_dir = Path(repo_config.project_dir)
            if not prj_dir.is_absolute():
                prj_dir = git_root / prj_dir
            logger.debug(f"Project dir from config: {prj_dir}")
            return prj_dir

        # No resolution - fail with clear message
        raise RuntimeError(
            "Project directory not specified. Use one of:\n"
            f"  1. CLI: --project-dir /path/to/projects\n"
            f"  2. Config: Set 'project_dir' in {git_root / GLOBAL_CONFIG_FILENAME}"
        )

    @staticmethod
    def _map_verbosity(args) -> LogLevel:
        """Map CLI verbosity flags to LogLevel enum"""
        if args.silent:
            return LogLevel.SILENT
        elif args.debug:
            return LogLevel.DEBUG
        elif args.verbose:
            return LogLevel.VERBOSE
        else:
            return LogLevel.NORMAL

    def execute_handler(
        self,
        handler_name: str,
        projects: list[str],
        options_dict: dict[str, Any],
        interactive: bool = False,
        return_handler: bool = False,
    ) -> Optional["BaseHandler"]:
        """
        Execute a handler with given projects and options.

        Args:
            handler_name: Name of handler to execute
            projects: list of project names
            options_dict: dictionary of handler options
            interactive: Whether running in interactive/menu mode
            return_handler: Whether to return the handler instance

        Returns:
            Handler instance if return_handler is True, otherwise None

        Raises:
            ValueError: If handler not found
            Exception: If handler execution fails
        """
        from hdlproject.handlers.registry import get_handler

        handler_info = get_handler(handler_name)
        if not handler_info:
            raise ValueError(f"Unknown handler: {handler_name}")

        # Log execution
        logger.info(f"{'='*60}")
        logger.info(f"Executing handler: {handler_name}")
        logger.info(f"Projects: {projects}")
        logger.info(f"Options: {options_dict}")
        logger.info(f"Interactive mode: {interactive}")
        logger.info(f"{'='*60}")

        # Create handler with RuntimeEnvironment
        handler = handler_info.create_handler(
            environment=self.runtime_environment,
            interactive=interactive,
        )
        options = handler_info.create_options(**options_dict)

        # Execute
        handler.execute(projects=projects, options=options)
        if return_handler:
            return handler
        return None

    def list_projects(self) -> list[str]:
        """Get list of available projects by scanning the projects directory."""
        projects_dir = self.runtime_environment.projects_base_dir
        if not projects_dir.exists():
            return []

        projects = []
        for d in projects_dir.iterdir():
            if not d.is_dir() or d.name.startswith("."):
                continue

            config_file = d / PROJECT_CONFIG_FILENAME
            if config_file.exists():
                projects.append(d.name)

        return sorted(projects)

    def get_handler_info(self, name: str):
        """Get handler information"""
        from hdlproject.handlers.registry import get_handler

        info = get_handler(name)
        if not info:
            raise ValueError(f"Handler not found: {name}")
        return info

    def get_menu_handlers(self, for_multiple_projects: bool = False):
        """Get handlers suitable for menu display"""
        from hdlproject.handlers.registry import get_menu_handlers

        return get_menu_handlers(for_multiple_projects)

    def shutdown(self):
        """Cleanup resources"""
        logger.info("Shutting down application")
        cleanup()
