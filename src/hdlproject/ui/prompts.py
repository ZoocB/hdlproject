# ui/prompts.py
"""Prompt factory and handlers for menu system"""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Set

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class BasePrompt(ABC):
    """Base class for all prompt types"""
    
    def __init__(self, style):
        self.style = style
    
    @abstractmethod
    def prompt(self, arg_def: dict[str, Any], context: str = "") -> Any:
        """Prompt user for value"""
        pass
    
    def get_help_text(self, arg_def: dict[str, Any]) -> str:
        """Get help text from argument definition"""
        arg_name = arg_def["name"].lstrip("-").replace("-", "_")
        return arg_def.get("help", f"Enter {arg_name}")


class BooleanPrompt(BasePrompt):
    """Handler for boolean prompts"""
    
    def prompt(self, arg_def: dict[str, Any], context: str = "") -> bool:
        """Prompt for boolean value"""
        try:
            message = self.get_help_text(arg_def)
            
            # Convert help text to question format if needed
            if not message.endswith("?"):
                message += "?"
            
            return inquirer.confirm(
                message=message,
                default=arg_def.get("default", False),
                style=self.style
            ).execute()
            
        except Exception as e:
            logger.debug(f"Error getting boolean input: {e}")
            return arg_def.get("default", False)


class NumberPrompt(BasePrompt):
    """Handler for number prompts"""
    
    def prompt(self, arg_def: dict[str, Any], context: str = "") -> int:
        """Prompt for number value"""
        try:
            arg_name = arg_def["name"].lstrip("-").replace("-", "_")
            help_text = self.get_help_text(arg_def)
            
            # Get bounds
            min_val, max_val, default_val = self._get_number_bounds(arg_name, arg_def)
            
            # Format message
            message = f"{help_text} ({min_val}-{max_val})"
            
            value = inquirer.number(
                message=message,
                default=default_val,
                min_allowed=min_val,
                max_allowed=max_val,
                style=self.style
            ).execute()
            
            return int(value)
            
        except Exception as e:
            logger.debug(f"Error getting number input: {e}")
            return arg_def.get("default", 1)
    
    def _get_number_bounds(self, arg_name: str, arg_def: dict[str, Any]) -> tuple[int, int, int]:
        """Get min, max, and default values for number prompt"""
        # Special handling for CPU cores
        if "cores" in arg_name:
            cpu_count = os.cpu_count() or 4
            max_val = max(1, cpu_count - 2)
            min_val = 1
            default_val = min(2, max_val)
        else:
            # Use provided bounds or defaults
            min_val = arg_def.get("min", 1)
            max_val = arg_def.get("max", 100)
            default_val = arg_def.get("default", min_val)
        
        return min_val, max_val, default_val


class TextPrompt(BasePrompt):
    """Handler for text prompts"""
    
    def prompt(self, arg_def: dict[str, Any], context: str = "") -> str:
        """Prompt for text value"""
        try:
            help_text = self.get_help_text(arg_def)
            default = arg_def.get("default", "")
            
            return inquirer.text(
                message=help_text,
                default=default,
                style=self.style
            ).execute()
            
        except Exception as e:
            logger.debug(f"Error getting text input: {e}")
            return arg_def.get("default", "")


class PathPrompt(BasePrompt):
    """Handler for path prompts"""
    
    def prompt(self, arg_def: dict[str, Any], context: str = "") -> Optional[str]:
        """Prompt for path value"""
        try:
            help_text = self.get_help_text(arg_def)
            default = arg_def.get("default", "./")
            
            return inquirer.filepath(
                message=help_text,
                default=default,
                style=self.style
            ).execute()
            
        except Exception as e:
            logger.debug(f"Error getting path input: {e}")
            return arg_def.get("default", None)


class ChoicePrompt(BasePrompt):
    """Handler for choice prompts"""
    
    def prompt(self, arg_def: dict[str, Any], context: str = "") -> str:
        """Prompt for choice selection"""
        try:
            help_text = self.get_help_text(arg_def)
            choices_list = arg_def.get("choices", [])
            
            if not choices_list:
                raise ValueError("No choices provided")
            
            # Format choices
            choice_objects = self._format_choices(choices_list, context)
            
            return inquirer.select(
                message=help_text,
                choices=choice_objects,
                style=self.style
            ).execute()
            
        except Exception as e:
            logger.debug(f"Error getting choice input: {e}")
            return choices_list[0] if choices_list else ""
    
    def _format_choices(self, choices: list[str], context: str) -> list[Choice]:
        """Format choices for display"""
        # Check if choices is a list of dicts with display names
        if choices and isinstance(choices[0], dict):
            return [
                Choice(
                    value=choice.get('value', choice.get('name', str(i))),
                    name=choice.get('display', choice.get('name', str(choice)))
                )
                for i, choice in enumerate(choices)
            ]
        
        # Simple string choices
        return [Choice(value=c, name=c) for c in choices]


class ArgumentAnalyser:
    """Analyses CLI arguments to determine what needs prompting"""
    
    @staticmethod
    def get_unprovided_arguments(args, handler_arguments: list[dict[str, Any]], 
                               handler_name: str) -> list[dict[str, Any]]:
        """
        Get arguments that weren't provided via CLI and need prompting.
        
        Args:
            args: Parsed command line arguments
            handler_arguments: list of argument definitions from handler
            handler_name: Name of the handler being executed
            
        Returns:
            list of argument definitions that need prompting
        """
        if not args:
            # If no args provided (pure menu mode), all optional args need prompting
            return [
                arg for arg in handler_arguments
                if arg["name"] != "projects"  # Projects are selected via menu
            ]
        
        # Get what was actually provided
        provided_args = ArgumentAnalyser._get_provided_arguments(args)
        
        # Determine what needs prompting
        unprovided = []
        for arg_def in handler_arguments:
            arg_name = ArgumentAnalyser._cli_to_python(arg_def["name"])
            
            # Skip if this is the projects argument (handled by menu)
            if arg_name == "projects":
                continue
            
            # Skip if value was provided via CLI
            if arg_name in provided_args:
                continue
            
            # This argument needs prompting
            unprovided.append(arg_def)
        
        return unprovided
    
    @staticmethod
    def _get_provided_arguments(args) -> Set[str]:
        """Extract which arguments were actually provided"""
        provided = set()
        
        if hasattr(args, '__dict__'):
            for key, value in vars(args).items():
                # Consider an argument provided if it has a non-None value
                # or if it's a boolean flag that was set
                if value is not None:
                    provided.add(key)
        
        return provided
    
    @staticmethod
    def _cli_to_python(cli_name: str) -> str:
        """Convert CLI argument name to Python attribute name"""
        # Remove leading dashes and convert to underscore
        return cli_name.lstrip("-").replace("-", "_")


class PromptFactory:
    """Factory for creating appropriate prompts with integrated argument handling"""
    
    def __init__(self, style):
        self.style = style
        self.prompts = {
            'boolean': BooleanPrompt(style),
            'number': NumberPrompt(style),
            'text': TextPrompt(style),
            'path': PathPrompt(style),
            'choice': ChoicePrompt(style)
        }
        self.argument_analyser = ArgumentAnalyser()
    
    def get_unprovided_arguments(self, args, handler_arguments: list[dict[str, Any]], 
                               handler_name: str) -> list[dict[str, Any]]:
        """Get arguments that need prompting - delegates to analyser"""
        return self.argument_analyser.get_unprovided_arguments(
            args, handler_arguments, handler_name
        )
    
    def prompt_for_argument(self, arg_def: dict[str, Any], context: str = "") -> Any:
        """Prompt user for a single argument value"""
        prompt_type = self._determine_prompt_type(arg_def)
        prompt_handler = self.prompts.get(prompt_type)
        
        if not prompt_handler:
            logger.warning(f"Unknown prompt type: {prompt_type}")
            return None
        
        return prompt_handler.prompt(arg_def, context)
    
    def cli_to_python(self, cli_name: str) -> str:
        """Convert CLI argument name to Python attribute name"""
        return ArgumentAnalyser._cli_to_python(cli_name)
    
    def _determine_prompt_type(self, arg_def: dict[str, Any]) -> str:
        """Determine which prompt type to use"""
        # Boolean
        if arg_def.get("action") == "store_true":
            return 'boolean'
        
        # Choice
        if arg_def.get("choices"):
            return 'choice'
        
        # Number
        if arg_def.get("type") == int:
            return 'number'
        
        # Path (heuristic based on name)
        arg_name = arg_def["name"].lstrip("-").replace("-", "_")
        if any(path_word in arg_name for path_word in ['dir', 'path', 'file']):
            return 'path'
        
        # Default to text
        return 'text'