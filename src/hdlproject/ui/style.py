# ui/style.py (Updated - no more JSON config)
"""Style management - uses defaults instead of JSON config"""

from typing import Any

from InquirerPy import get_style
from hdlproject.utils.logging_manager  import get_logger

logger = get_logger(__name__)


class StyleManager:
    """Manages UI styling with built-in defaults"""
    
    def __init__(self):
        self.colors = self._default_colors()
        self.styles = self._default_styles()
        self.symbols = self._default_symbols()
    
    def _default_colors(self) -> dict[str, str]:
        """Default color scheme"""
        return {
            "primary": "#ff9d00",
            "secondary": "#5f819d", 
            "disabled": "#858585",
            "error": "#ff0000",
            "success": "#00ff00",
            "warning": "#ffff00",
            "default": "#ffffff"
        }
    
    def _default_styles(self) -> dict[str, dict[str, Any]]:
        """Default style definitions"""
        return {
            "questionmark": {"foreground": "primary", "bold": True},
            "pointer": {"foreground": "primary", "bold": True},
            "answer": {"foreground": "secondary"},
            "question": {"foreground": "default"},
            "selected": {"foreground": "secondary", "bold": True},
            "disabled": {"foreground": "disabled", "italic": True}
        }
    
    def _default_symbols(self) -> dict[str, str]:
        """Default symbols"""
        return {
            "questionmark": "?",
            "pointer": "→",
            "answer": "→",
            "separator": "─"*30
        }
    
    def get_inquirer_style(self) -> tuple[dict[str, str], dict[str, str]]:
        """Get InquirerPy style configuration"""
        style_dict = {}
        
        style_mapping = {
            "questionmark": "questionmark",
            "selected": "selected", 
            "pointer": "pointer",
            "answer": "answer",
            "question": "question",
            "disabled": "disabled"
        }
        
        for our_key, inquirer_key in style_mapping.items():
            if our_key in self.styles:
                style_str = self._build_style_string(self.styles[our_key])
                if style_str:
                    style_dict[inquirer_key] = style_str
        
        return get_style(style_dict, style_override=True)
    
    def _build_style_string(self, style: dict[str, Any]) -> str:
        """Build style string from configuration"""
        parts = []
        
        if "foreground" in style:
            color_name = style["foreground"]
            if color_name in self.colors:
                color = self.colors[color_name]
                if color.startswith("#"):
                    color = color[1:]
                parts.append(f"fg:#{color}")
        
        if style.get("bold"):
            parts.append("bold")
        if style.get("italic"):
            parts.append("italic")
        if style.get("underline"):
            parts.append("underline")
        
        return " ".join(parts)