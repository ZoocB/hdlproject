# core/application.py
"""Application container with internal initialisation"""

import subprocess
import shutil
from pathlib import Path
from typing import Any

from hdlproject.config.repository import RepositoryConfigManager
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
    ):
        """
        Initialise application with resolved configuration.

        Args:
            git_root: Git repository root
            project_dir: Projects base directory
            compile_order_format: Compile order output format
            verbosity: Logging verbosity level
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

        # Create handler environment (replaces BaseHandler.Initialise)
        self.handler_environment = {
            "project_dir": project_dir,
            "repository_root": git_root,
            "vivado_location": Path("/tools/Xilinx/Vivado"),
            "compile_order_format": compile_order_format,
        }

        # Load all handlers
        load_all_handlers()

        logger.info("Application Initialised")
        logger.info(f"Git root: {git_root}")
        logger.info(f"Project dir: {project_dir}")
        logger.info(f"Compile order format: {compile_order_format}")

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
        repo_config = RepositoryConfigManager(git_root).load()
        compile_format = (
            getattr(args, "compile_order_format", None)
            or repo_config.compile_order_script_format
            or "json"
        )

        # Step 5: Map verbosity from args
        verbosity = cls._map_verbosity(args)

        # Create instance
        return cls(
            git_root=git_root,
            project_dir=project_dir,
            compile_order_format=compile_format,
            verbosity=verbosity,
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
        repo_config = RepositoryConfigManager(git_root).load()

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
            f"  2. Config: Set 'project_dir' in {git_root / 'hdlproject_config.json'}"
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
    ) -> None:
        """
        Execute a handler with given projects and options.

        Args:
            handler_name: Name of handler to execute
            projects: list of project names
            options_dict: dictionary of handler options
            interactive: Whether running in interactive/menu mode

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

        # Create handler with environment and options
        handler = handler_info.create_handler(
            environment=self.handler_environment, interactive=interactive
        )
        options = handler_info.create_options(**options_dict)

        # Execute
        handler.execute(projects=projects, options=options)
        if return_handler:
            return handler
        return None

    def list_projects(self) -> list[str]:
        """Get list of available projects"""
        from hdlproject.handlers.registry import get_handler

        # Use any handler to get project list
        handler_info = get_handler("build")
        if handler_info:
            handler = handler_info.create_handler(
                environment=self.handler_environment, interactive=False
            )
            return handler.get_project_list()
        return []

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
