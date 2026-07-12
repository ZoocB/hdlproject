# utils/logging_manager.py
"""Unified logging management system

Library-safety invariant: importing this module (or anything that imports
it) must never touch the root logger or attach any handlers. All package
output is anchored on the "hdlproject" logger, which is only configured the
first time a caller explicitly asks for CLI-style logging (via
``set_verbosity``). Root is only ever touched by ``setup_application_log``,
which is exclusively invoked by the CLI application itself.
"""

import logging
import sys
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

# Namespace logger for this module's own diagnostics - never the root logger.
logger = logging.getLogger(__name__)

PACKAGE_LOGGER_NAME = "hdlproject"


class LogLevel(Enum):
    """Simplified verbosity levels"""
    SILENT = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3


class LoggingManager:
    """Centralised logging manager for application and project logs"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_Initialised'):
            self._Initialised = True
            self.log_level = LogLevel.NORMAL
            self.app_log_path: Optional[Path] = None
            self.project_logs: dict[str, logging.FileHandler] = {}
            self._console_handler: Optional[logging.StreamHandler] = None
            self._app_file_handler: Optional[logging.FileHandler] = None

    def _ensure_console_handler(self) -> None:
        """Attach the console handler to the package logger, on first use.

        Anchored on "hdlproject" (not root) with propagate=False, so console
        output never duplicates into a host application's root handlers.
        """
        if self._console_handler is not None:
            return

        package_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
        package_logger.setLevel(logging.DEBUG)
        package_logger.propagate = False

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(self._get_console_level())
        console.setFormatter(self._get_console_formatter())
        package_logger.addHandler(console)
        self._console_handler = console

    def setup_application_log(self, log_dir: Path) -> Path:
        """Setup main application log file.

        Only called when running as the CLI application (never at import).
        Attaches to the ROOT logger, deliberately, so third-party library
        logs are also captured - existing root handlers are left intact.
        """
        log_dir.mkdir(parents=True, exist_ok=True)
        self.app_log_path = log_dir / "hdlproject.log"

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(self.app_log_path, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        root.addHandler(file_handler)
        # The package logger does not propagate to root, so the file handler
        # must also be attached there for hdlproject's own logs to be
        # captured alongside third-party output. Each record passes through
        # exactly one of the two loggers, so nothing is written twice.
        logging.getLogger(PACKAGE_LOGGER_NAME).addHandler(file_handler)
        self._app_file_handler = file_handler

        # Log startup
        logger.info("="*60)
        logger.info("Project Manager Started")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Log: {self.app_log_path}")
        logger.info("="*60)

        return self.app_log_path

    def setup_project_log(self, project_name: str, log_path: Path) -> None:
        """Setup project-specific log file"""
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create project logger
        project_logger = logging.getLogger(f"hdlproject.project.{project_name}")
        project_logger.setLevel(logging.DEBUG)
        project_logger.propagate = False  # Don't propagate to root

        # Clear any existing handlers
        project_logger.handlers.clear()

        # Add file handler for project
        file_handler = logging.FileHandler(log_path, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        project_logger.addHandler(file_handler)

        # Also add console handler for project logs if not silent
        if self.log_level != LogLevel.SILENT:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self._get_console_level())
            console_handler.setFormatter(self._get_console_formatter())
            project_logger.addHandler(console_handler)

        self.project_logs[project_name] = file_handler

        # Log project start
        project_logger.info(f"Project log started: {project_name}")
        project_logger.info(f"Log file: {log_path}")

    def get_project_logger(self, project_name: str) -> logging.Logger:
        """Get logger for specific project"""
        return logging.getLogger(f"hdlproject.project.{project_name}")

    def set_verbosity(self, level: LogLevel):
        """Update verbosity level"""
        self.log_level = level
        self._ensure_console_handler()
        self._console_handler.setLevel(self._get_console_level())
        self._console_handler.setFormatter(self._get_console_formatter())

        # Update project loggers
        for project_name in self.project_logs:
            project_logger = self.get_project_logger(project_name)
            for handler in project_logger.handlers:
                if (
                    isinstance(handler, logging.StreamHandler)
                    and handler != self.project_logs[project_name]
                ):
                    handler.setLevel(self._get_console_level())
                    handler.setFormatter(self._get_console_formatter())

    def _get_console_level(self) -> int:
        """Map LogLevel to logging level for console"""
        mapping = {
            LogLevel.SILENT: logging.CRITICAL + 10,
            LogLevel.NORMAL: logging.WARNING,
            LogLevel.VERBOSE: logging.INFO,
            LogLevel.DEBUG: logging.DEBUG
        }
        return mapping[self.log_level]

    def _get_console_formatter(self) -> logging.Formatter:
        """Get appropriate formatter based on verbosity"""
        if self.log_level == LogLevel.DEBUG:
            return logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        elif self.log_level == LogLevel.VERBOSE:
            return logging.Formatter('[%(levelname)s] %(message)s')
        else:
            return logging.Formatter('%(message)s')

    def is_silent(self) -> bool:
        """Check if in silent mode"""
        return self.log_level == LogLevel.SILENT

    def should_show_status_display(self) -> bool:
        """Check if status display should be shown"""
        return self.log_level != LogLevel.SILENT

    def cleanup(self):
        """Cleanup all handlers this manager attached"""
        for handler in self.project_logs.values():
            handler.close()
        self.project_logs.clear()

        if self._console_handler is not None:
            logging.getLogger(PACKAGE_LOGGER_NAME).removeHandler(self._console_handler)
            self._console_handler.close()
            self._console_handler = None

        if self._app_file_handler is not None:
            logging.getLogger().removeHandler(self._app_file_handler)
            logging.getLogger(PACKAGE_LOGGER_NAME).removeHandler(
                self._app_file_handler
            )
            self._app_file_handler.close()
            self._app_file_handler = None


# Global instance. Safe to build eagerly: __init__ only sets plain
# attributes and never touches the root logger or attaches handlers.
_manager = LoggingManager()

# Convenience functions
def setup_application_log(log_dir: Path) -> Path:
    return _manager.setup_application_log(log_dir)

def setup_project_log(project_name: str, log_path: Path):
    _manager.setup_project_log(project_name, log_path)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)

def get_project_logger(project_name: str) -> logging.Logger:
    """Get project-specific logger"""
    return _manager.get_project_logger(project_name)

def set_verbosity(level: LogLevel):
    _manager.set_verbosity(level)

def is_silent() -> bool:
    return _manager.is_silent()

def should_show_status_display() -> bool:
    return _manager.should_show_status_display()

def cleanup():
    _manager.cleanup()
