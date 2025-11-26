# main.py
"""Entry point for hdlproject"""

import sys

from hdlproject.core.application import Application
from hdlproject.cli.parser import create_parser
from hdlproject.ui.menu import ProjectManagementMenu
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


def main() -> int:
    """Main entry point - routes to either interactive menu or batch command execution"""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Create application - it handles all initialisation internally
        app = Application.from_args(args)

        if args.command:
            # BATCH MODE: Execute single command and exit
            logger.info(f"Batch mode: executing command '{args.command}'")
            return _execute_batch_command(app, args)
        else:
            # INTERACTIVE MODE: Launch menu (which uses batch commands under the hood)
            logger.info("Interactive mode: launching menu")
            return _run_interactive_menu(app, args)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        if "app" in locals():
            app.shutdown()


def _execute_batch_command(app: Application, args) -> int:
    """Execute a single batch command with projects and options"""
    try:
        # Extract CLI options that match handler parameters
        cli_options = _extract_cli_options(args)

        # Execute handler in batch mode
        app.execute_handler(
            handler_name=args.command,
            projects=args.projects,
            options_dict=cli_options,
            interactive=False,
        )
        return 0

    except ValueError as e:
        logger.error(f"Invalid command: {e}")
        return 1
    except Exception as e:
        logger.error(f"Command failed: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return 1


def _run_interactive_menu(app: Application, args) -> int:
    """Run interactive menu mode"""
    menu = ProjectManagementMenu(app, args)
    menu.run()
    return 0


def _extract_cli_options(args) -> dict:
    """
    Extract option values from parsed args for handler execution.

    Filters out framework arguments and returns only handler-specific options.
    """
    # Framework arguments to exclude
    framework_args = {
        "command",
        "projects",
        "project_dir",
        "compile_order_format",
        "debug",
        "verbose",
        "silent",
    }

    # Extract all other arguments as handler options
    options = {}
    for key, value in vars(args).items():
        if key not in framework_args and value is not None:
            options[key] = value

    return options


if __name__ == "__main__":
    sys.exit(main())
