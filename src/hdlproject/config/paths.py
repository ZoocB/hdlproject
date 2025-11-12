# config/paths.py
"""Path-related dataclasses - no dependencies to avoid circular imports"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class OperationPaths:
    """Standardised paths for any operation"""
    operation_dir: Path
    logs_dir: Path
    project_dir: Path
    bd_dir: Path
    xci_dir: Path
    
    def get_log_file(self, operation: str) -> Path:
        """Get log file path for operation"""
        return self.logs_dir / f"{operation}.log"
    
    def get_project_file(self, project_name: str) -> Path:
        """Get .xpr project file path"""
        return self.project_dir / f"{project_name}.xpr"
    
    def create_directories(self) -> None:
        """Create all operation directories"""
        for path in [self.logs_dir, self.project_dir, self.bd_dir, self.xci_dir]:
            path.mkdir(parents=True, exist_ok=True)