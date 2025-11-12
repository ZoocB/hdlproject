# cli/parser.py
"""Command line interface parser"""

import argparse


def create_parser() -> argparse.ArgumentParser:
    """
    Create command line argument parser.
    
    Structure:
    - Global framework options (project_dir, verbosity, etc.)
    - Handler subcommands (dynamically loaded from registry)
    """
    parser = argparse.ArgumentParser(
        description="HDL Project Management System for Vivado Projects",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # === Global Framework Options ===
    
    parser.add_argument(
        '--project-dir',
        type=str,
        default=None,
        help='Project directory (overrides hdlproject-config.json)'
    )
    
    parser.add_argument(
        '--compile-order-format',
        choices=['txt', 'csv', 'json'],
        default="json",
        help='Compile order output format (overrides config, default: json)'
    )
    
    # Verbosity options (mutually exclusive)
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    verbosity_group.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    verbosity_group.add_argument(
        '--silent',
        action='store_true',
        help='Disable console output (logs still written)'
    )
    
    # === Handler Subcommands ===
    
    subparsers = parser.add_subparsers(
        dest='command', 
        help='Available commands (omit for interactive menu)'
    )
    
    # Load handler commands dynamically
    try:
        from hdlproject.handlers.registry import get_all_handlers, load_all_handlers
        
        load_all_handlers()
        handlers = get_all_handlers()
        
        for handler_name, handler_info in handlers.items():
            # Create subparser for this handler
            cmd_parser = subparsers.add_parser(
                handler_name,
                help=handler_info.description
            )
            
            # Add handler-specific arguments
            for arg_def in handler_info.cli_arguments:
                arg_def_copy = arg_def.copy()
                arg_name = arg_def_copy.pop("name")
                cmd_parser.add_argument(arg_name, **arg_def_copy)
                
    except Exception as e:
        # Allow parser to work even if handlers fail to load
        # This enables --help to work during development
        pass
    
    return parser