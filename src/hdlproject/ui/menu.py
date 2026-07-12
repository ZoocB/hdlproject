# ui/menu.py
"""Interactive keyboard-driven menu (project selection + operation prompts)."""
from typing import Any

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from hdlproject.core.application import Application
from hdlproject.ui.prompts import PromptFactory
from hdlproject.ui.style import StyleManager
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class ProjectManagementMenu:
    """Interactive menu for project management"""

    # Color codes
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    def __init__(self, app: Application, args=None):
        """
        Initialise menu with application instance.
        Args:
            app: Application instance (required)
            args: Command line arguments for hybrid mode
        """
        self.app = app
        self.args = args
        self.style_manager = StyleManager()
        self.prompt_factory = PromptFactory(self.style_manager.get_inquirer_style())
        self._selected_projects: list[str] = []
        self._style = self.style_manager.get_inquirer_style()

    def run(self) -> None:
        """Run the interactive menu system"""
        try:
            self._display_header()
            # Select projects
            if not self._select_projects():
                logger.info("No projects selected. Exiting.")
                return
            self._display_project_summary()
            # Main menu loop
            self._handle_menu()
        except KeyboardInterrupt:
            logger.info("\nMenu cancelled by user.")
        except Exception as e:
            logger.error(f"Menu error: {e}")
            raise

    def _display_header(self) -> None:
        """Display application header"""
        header_text = """
╔══════════════════════════════════════════════════╗
║          HDL Project Management System           ║
╚══════════════════════════════════════════════════╝
"""
        print(header_text)

    def _select_projects(self) -> bool:
        """Handle project selection"""
        projects = self.app.list_projects()
        if not projects:
            logger.error("No projects found")
            return False
        # Create project choices
        choices: list[Choice | Separator] = [Choice(project) for project in projects]
        choices.append(Separator())
        self._selected_projects = inquirer.checkbox(
            message="Select project(s):",
            choices=choices,
            validate=lambda result: len(result) >= 1,
            invalid_message="Please select at least one project",
            instruction="Use space to select, enter to confirm",
            style=self._style,
            qmark="?",
            pointer="→",
        ).execute()
        return len(self._selected_projects) > 0

    def _display_project_summary(self) -> None:
        """Display selected projects summary"""
        print(f"\n{'='*30}")
        print(f"Selected Projects ({len(self._selected_projects)}):")
        print(f"{'='*30}")
        for i, project in enumerate(self._selected_projects, 1):
            print(f"{i}. {project}")
        print(f"{'='*30}\n")

    def _handle_menu(self) -> None:
        """Handle main menu navigation"""
        while True:
            try:
                choices = self._create_menu_choices()
                action = inquirer.select(
                    message="Select an action:",
                    choices=choices,
                    style=self._style,
                    qmark="?",
                    pointer="→",
                ).execute()
                if action == "exit":
                    self._show_exit_message()
                    return
                self._execute_handler(action)
            except KeyboardInterrupt:
                logger.info("\nMenu cancelled by user.")
                return
            except Exception as e:
                logger.error(f"Menu error: {e}")
                if not self._confirm_continue():
                    return

    def _create_menu_choices(self) -> list[Choice | Separator]:
        """Create menu choices from handler registry"""
        choices: list[Choice | Separator] = []
        is_multi = len(self._selected_projects) > 1
        # Get handlers from application
        menu_handlers = self.app.get_menu_handlers(for_multiple_projects=is_multi)
        for handler_name, handler_info in menu_handlers:
            display_name = f"{handler_info.menu_name}"
            choices.append(Choice(handler_name, name=display_name))
        # Add separator and exit
        if choices:
            choices.append(Separator("─" * 20))
        choices.append(Choice("exit", name="Exit"))
        return choices

    def _execute_handler(self, handler_name: str) -> None:
        """Execute the selected handler, surfacing any failure to the user."""
        error_message = None
        try:
            handler_info = self.app.get_handler_info(handler_name)
            options_dict = self._collect_handler_options(handler_info)
            self.app.execute_handler(
                handler_name=handler_name,
                projects=self._selected_projects,
                options_dict=options_dict,
                interactive=True,
            )
        except RuntimeError as e:
            error_message = str(e)
        except Exception as e:
            error_message = f"Unexpected error: {e}"
        finally:
            if error_message:
                # Surface the failure instead of silently returning to the menu.
                logger.error(error_message)
                print(f"\n{self.RED}{self.BOLD}✗ {error_message}{self.RESET}")
            input("\nPress Enter to continue...")

    def _collect_handler_options(self, handler_info) -> dict[str, Any]:
        """Collect options for handler through prompts"""
        options_dict = {}
        # Determine which arguments need prompting
        unprovided_args = self.prompt_factory.get_unprovided_arguments(
            self.args, handler_info.cli_arguments, handler_info.name
        )
        # Prompt for each unprovided argument
        for arg_def in unprovided_args:
            arg_name = self.prompt_factory.cli_to_python(arg_def["name"])
            value = self.prompt_factory.prompt_for_argument(arg_def, handler_info.name)
            # Only include non-None values
            if value is not None:
                options_dict[arg_name] = value
        return options_dict

    def _confirm_continue(self) -> bool:
        """Ask user if they want to continue"""
        return inquirer.confirm(
            message="Return to main menu?", default=True, style=self._style
        ).execute()

    def _show_exit_message(self) -> None:
        """Show exit message"""
        print("\n" + "=" * 50)
        print("Thank you for using HDL Project Management System")
        print("=" * 50 + "\n")
