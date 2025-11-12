# utils/logging_manager.py
"""Unified logging management system"""

import logging
import sys
from pathlib import Path
from typing import Optional
from enum import Enum
from datetime import datetime
import threading


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
            self._setup_root_logger()
    
    def _setup_root_logger(self):
        """Setup root logger with console handler only initially"""
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        
        # Remove any existing handlers
        root.handlers.clear()
        
        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(self._get_console_level())
        console.setFormatter(self._get_console_formatter())
        root.addHandler(console)
        self._console_handler = console
    
    def setup_application_log(self, log_dir: Path) -> Path:
        """Setup main application log file"""
        log_dir.mkdir(parents=True, exist_ok=True)
        self.app_log_path = log_dir / "hdlproject.log"
        
        # Add file handler to root logger
        root = logging.getLogger()
        file_handler = logging.FileHandler(self.app_log_path, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        root.addHandler(file_handler)
        
        # Log startup
        logging.info("="*60)
        logging.info("Project Manager Started")
        logging.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"Log: {self.app_log_path}")
        logging.info("="*60)
        
        return self.app_log_path
    
    def setup_project_log(self, project_name: str, log_path: Path) -> None:
        """Setup project-specific log file"""
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create project logger
        project_logger = logging.getLogger(f"project.{project_name}")
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
        return logging.getLogger(f"project.{project_name}")
    
    def set_verbosity(self, level: LogLevel):
        """Update verbosity level"""
        self.log_level = level
        self._console_handler.setLevel(self._get_console_level())
        self._console_handler.setFormatter(self._get_console_formatter())
        
        # Update project loggers
        for project_name in self.project_logs:
            project_logger = self.get_project_logger(project_name)
            for handler in project_logger.handlers:
                if isinstance(handler, logging.StreamHandler) and handler != self.project_logs[project_name]:
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
            return logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        """Cleanup all handlers"""
        for handler in self.project_logs.values():
            handler.close()
        self.project_logs.clear()


# Global instance
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