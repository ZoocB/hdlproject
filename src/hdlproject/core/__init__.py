# core/__init__.py
"""Core functionality for project management"""

from hdlproject.core.application import Application
from hdlproject.core.compile_order import CompileOrderManager
from hdlproject.core.output_processor import VivadoOutputProcessor
from hdlproject.core.application import Application

__all__ = [
    "Application",
    "CompileOrderManager",
    "VivadoOutputProcessor",
    "Application",
]
