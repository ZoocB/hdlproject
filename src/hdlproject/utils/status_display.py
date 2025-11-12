# utils/status_display.py
"""Simplified status display with tree visualization"""

import time
import threading
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich import box
from rich.text import Text
from rich.tree import Tree

from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


class DisplayMode(Enum):
    """Display modes for status output"""
    INTERACTIVE = "interactive"
    SILENT = "silent"


class StepState(Enum):
    """States for individual steps"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MessageLevel(Enum):
    """Message severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Step:
    """Individual step in a process"""
    name: str
    state: StepState = StepState.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def get_duration_str(self) -> str:
        """Get formatted duration string"""
        if not self.start_time:
            return ""
        
        end_time = self.end_time or datetime.now()
        duration = int((end_time - self.start_time).total_seconds())
        
        if duration < 60:
            return f"{duration}s"
        else:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes:02d}:{seconds:02d}"


@dataclass
class ProjectMessage:
    """Message associated with a project"""
    level: MessageLevel
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProjectStatus:
    """Status tracking for a single project"""
    name: str
    steps: list[Step] = field(default_factory=list)
    current_step_index: int = -1
    overall_state: StepState = StepState.PENDING
    start_time: Optional[datetime] = None
    message: Optional[str] = None
    log_file_path: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    # Message tracking
    messages: list[ProjectMessage] = field(default_factory=list)
    message_counts: dict[MessageLevel, int] = field(default_factory=lambda: defaultdict(int))
    
    def get_elapsed_time(self) -> str:
        """Get total elapsed time"""
        if not self.start_time:
            return "00:00"
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def add_message(self, level: MessageLevel, message: str) -> None:
        """Add a message to this project"""
        with self._lock:
            self.messages.append(ProjectMessage(level, message))
            self.message_counts[level] += 1
    
    def get_latest_message(self) -> Optional[ProjectMessage]:
        """Get the most recent message"""
        with self._lock:
            # Only return warnings, critical warnings, or errors
            relevant_messages = [
                msg for msg in self.messages 
                if msg.level in [MessageLevel.WARNING, MessageLevel.ERROR, MessageLevel.CRITICAL]
            ]
            return relevant_messages[-1] if relevant_messages else None
    
    def get_message_summary(self) -> str:
        """Get message count summary"""
        with self._lock:
            parts = []
            if self.message_counts[MessageLevel.WARNING] > 0:
                parts.append(f"W:{self.message_counts[MessageLevel.WARNING]}")
            if self.message_counts[MessageLevel.CRITICAL] > 0:
                parts.append(f"C:{self.message_counts[MessageLevel.CRITICAL]}")
            if self.message_counts[MessageLevel.ERROR] > 0:
                parts.append(f"E:{self.message_counts[MessageLevel.ERROR]}")
            return " ".join(parts) if parts else ""
    
    def start_step(self, step_name: str) -> None:
        """Start a specific step - thread-safe"""
        with self._lock:
            # Complete current step if running
            if self.current_step_index >= 0:
                current = self.steps[self.current_step_index]
                if current.state == StepState.RUNNING:
                    current.state = StepState.COMPLETED
                    current.end_time = datetime.now()
            
            # Find and start the new step
            for i, step in enumerate(self.steps):
                if step.name == step_name:
                    # Mark skipped steps
                    for j in range(self.current_step_index + 1, i):
                        if self.steps[j].state == StepState.PENDING:
                            self.steps[j].state = StepState.SKIPPED
                    
                    # Start new step
                    step.state = StepState.RUNNING
                    step.start_time = datetime.now()
                    self.current_step_index = i
                    break
    
    def fail(self, message: Optional[str] = None) -> None:
        """Mark project as failed - thread-safe"""
        with self._lock:
            self.overall_state = StepState.FAILED
            self.message = message
            
            # Mark current step as failed
            if self.current_step_index >= 0:
                step = self.steps[self.current_step_index]
                step.state = StepState.FAILED
                step.end_time = datetime.now()
            
            # Skip remaining steps
            for i in range(self.current_step_index + 1, len(self.steps)):
                if self.steps[i].state == StepState.PENDING:
                    self.steps[i].state = StepState.SKIPPED
    
    def complete(self) -> None:
        """Mark project as completed - thread-safe"""
        with self._lock:
            self.overall_state = StepState.COMPLETED
            
            # Complete current step if running
            if self.current_step_index >= 0:
                step = self.steps[self.current_step_index]
                if step.state == StepState.RUNNING:
                    step.state = StepState.COMPLETED
                    step.end_time = datetime.now()
            
            # Skip remaining steps
            for step in self.steps:
                if step.state == StepState.PENDING:
                    step.state = StepState.SKIPPED


class LiveStatusDisplay:
    """Simplified live status display"""
    
    def __init__(self, title: str, mode: DisplayMode = DisplayMode.INTERACTIVE):
        """
        Initialise status display.
        
        Args:
            title: Display title
            mode: Display mode (interactive or silent)
        """
        self.title = title
        self.mode = mode
        
        self.projects: dict[str, ProjectStatus] = {}
        self._running = False
        self._lock = threading.RLock()
        
        # All messages (for final summary)
        self._all_messages: list[tuple[str, ProjectMessage]] = []
        
        if mode == DisplayMode.INTERACTIVE:
            self.console = Console()
            self.live = None
            self._display_thread = None

    def start_project(self, project_name: str) -> None:
        """Start a project - transition from pending to running"""
        with self._lock:
            if project_name not in self.projects:
                logger.warning(f"Cannot start unknown project: {project_name}")
                return
            
            project = self.projects[project_name]
            if project.overall_state == StepState.PENDING:
                project.overall_state = StepState.RUNNING
                project.start_time = datetime.now()
                logger.debug(f"Project {project_name} started")
    
    def add_project(self, project_name: str, steps: list[str]) -> None:
        """Add a project with predefined steps"""
        with self._lock:
            project_steps = [Step(name=step) for step in steps]
            self.projects[project_name] = ProjectStatus(
                name=project_name,
                steps=project_steps
            )
    
    def set_project_log_file(self, project_name: str, log_file_path: str) -> None:
        """Set the log file path for a project"""
        with self._lock:
            if project_name in self.projects:
                self.projects[project_name].log_file_path = log_file_path
    
    def update_project_step(self, project_name: str, step_name: str, 
                           failed: bool = False, message: Optional[str] = None) -> None:
        """Update project to a specific step"""
        with self._lock:
            if project_name not in self.projects:
                return
            
            project = self.projects[project_name]
            
            # Start project if not started
            if not project.start_time:
                project.start_time = datetime.now()
                project.overall_state = StepState.RUNNING
            
            if failed:
                project.fail(message)
            else:
                project.start_step(step_name)
    
    def complete_project(self, project_name: str, success: bool = True, 
                        message: Optional[str] = None) -> None:
        """Mark a project as completed"""
        with self._lock:
            if project_name not in self.projects:
                return
            
            project = self.projects[project_name]
            if success:
                project.complete()
            else:
                project.fail(message)
    
    def add_message(self, level: MessageLevel, message: str) -> None:
        """Add a message at specified level"""
        with self._lock:
            self._all_messages.append(("_global", ProjectMessage(level, message)))
    
    def process_output(self, line: str, project_name: str) -> None:
        """Process output line - simplified for vivado parser integration"""
        # This is handled by the output processor now
        pass
    
    def start_display(self) -> None:
        """Start the display"""
        if self.mode != DisplayMode.INTERACTIVE:
            return
        
        self._running = True
        
        # Start Rich Live display with screen=True to prevent scrolling
        self.live = Live(
            self._generate_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
            screen=True
        )
        self.live.start()
        
        # Start update thread
        self._display_thread = threading.Thread(target=self._update_loop)
        self._display_thread.daemon = True
        self._display_thread.start()
    
    def stop_display(self) -> None:
        """Stop the display and show final state"""
        if self.mode != DisplayMode.INTERACTIVE:
            return
        
        self._running = False
        
        if self._display_thread:
            self._display_thread.join(timeout=1.0)
        
        if self.live:
            try:
                # Update one final time
                self.live.update(self._generate_display())
                time.sleep(0.5)
                self.live.stop()
                
                # Print final summary
                self._print_final_summary()
            except:
                pass
    
    def _print_final_summary(self) -> None:
        """Print minimal final summary after live display stops"""
        with self._lock:
            success_count = 0
            failed_count = 0
            projects_with_issues = []
            
            for project_name, project in sorted(self.projects.items()):
                if project.overall_state == StepState.COMPLETED:
                    success_count += 1
                    # Check if completed but with warnings/errors
                    if project.message_counts[MessageLevel.WARNING] > 0 or \
                       project.message_counts[MessageLevel.ERROR] > 0 or \
                       project.message_counts[MessageLevel.CRITICAL] > 0:
                        projects_with_issues.append(project_name)
                elif project.overall_state == StepState.FAILED:
                    failed_count += 1
            
            # Single line summary
            print()  # Empty line for spacing
            if failed_count > 0:
                print(f"{self.title}: {failed_count} failed, {success_count} succeeded")
            elif success_count > 0:
                if not projects_with_issues:
                    print(f"{self.title}: All {success_count} succeeded")
                else:
                    print(f"{self.title}: Some {success_count} succeeded")
            else:
                print(f"{self.title}: No projects processed")
            
            # Show message summary only if there were issues
            if failed_count > 0 or projects_with_issues:
                self._print_message_summary()
    
    def _print_message_summary(self) -> None:
        """Print summary of warnings/errors"""
        with self._lock:
            # Group messages by project
            project_messages = defaultdict(list)
            
            for project_name, msg in self._all_messages:
                if msg.level in [MessageLevel.WARNING, MessageLevel.ERROR, MessageLevel.CRITICAL]:
                    project_messages[project_name].append(msg)
            
            # Also collect from project status
            for project_name, project in self.projects.items():
                for msg in project.messages:
                    if msg.level in [MessageLevel.WARNING, MessageLevel.ERROR, MessageLevel.CRITICAL]:
                        project_messages[project_name].append(msg)
            
            if not project_messages:
                return
            
            print("\nWarnings/Errors Summary:")
            print("─" * 60)
            
            for project_name in sorted(project_messages.keys()):
                if project_name == "_global":
                    continue  # Handle global messages separately
                    
                messages = project_messages[project_name]
                if not messages:
                    continue
                
                print(f"\n{project_name}:")
                
                # Show last 5 messages for this project
                recent_messages = messages[-5:]
                for msg in recent_messages:
                    level_str = msg.level.name
                    # Truncate long messages
                    msg_text = msg.message
                    if len(msg_text) > 70:
                        msg_text = msg_text[:67] + "..."
                    print(f"  [{level_str}] {msg_text}")
                
                if len(messages) > 5:
                    print(f"  ... and {len(messages) - 5} more")
            
            # Handle global messages if any
            if "_global" in project_messages:
                global_msgs = project_messages["_global"][-5:]
                if global_msgs:
                    print("\nGeneral:")
                    for msg in global_msgs:
                        level_str = msg.level.name
                        msg_text = msg.message
                        if len(msg_text) > 70:
                            msg_text = msg_text[:67] + "..."
                        print(f"  [{level_str}] {msg_text}")
    
    def _update_loop(self) -> None:
        """Update loop for Rich display"""
        while self._running and self.live:
            try:
                # Update display
                self.live.update(self._generate_display())
                time.sleep(0.25)
            except:
                pass
    
    def _generate_display(self) -> Panel:
        """Generate Rich display panel using tree view"""
        with self._lock:
            tree = Tree(f"[bold cyan]{self.title}[/bold cyan]")
            
            # Group projects by state
            groups = {
                StepState.RUNNING: [],
                StepState.COMPLETED: [],
                StepState.FAILED: [],
                StepState.PENDING: []
            }
            
            for name, project in self.projects.items():
                groups[project.overall_state].append((name, project))
            
            # Define simple theme
            state_theme = {
                StepState.PENDING: ("○", "dim white"),
                StepState.RUNNING: ("►", "cyan"),
                StepState.COMPLETED: ("✓", "green"),
                StepState.FAILED: ("✗", "red"),
                StepState.SKIPPED: ("—", "dim yellow"),
            }
            
            step_theme = {
                StepState.PENDING: ("·", "dim white"),
                StepState.RUNNING: ("►", "cyan"),
                StepState.COMPLETED: ("✓", "green"),
                StepState.FAILED: ("✗", "red"),
                StepState.SKIPPED: ("—", "dim yellow"),
            }
            
            # Add groups to tree
            for state, projects in groups.items():
                if not projects:
                    continue
                    
                symbol, color = state_theme[state]
                state_name = state.name.title()
                branch = tree.add(f"[{color}]{symbol} {state_name} ({len(projects)})[/{color}]")
                
                for name, project in sorted(projects):
                    # Build project entry with message counts
                    project_text = f"[bold]{name}[/bold]"
                    
                    # Add message summary if any
                    msg_summary = project.get_message_summary()
                    if msg_summary:
                        project_text += f" [{msg_summary}]"
                    
                    # Add elapsed time for running projects
                    if state == StepState.RUNNING:
                        project_text += f" [{project.get_elapsed_time()}]"
                    
                    if state == StepState.RUNNING and project.steps:
                        # Show detailed progress for running projects
                        project_branch = branch.add(project_text)
                        
                        # Show steps
                        for step in project.steps:
                            if step.state != StepState.PENDING:
                                step_symbol, step_color = step_theme[step.state]
                                duration = f" ({step.get_duration_str()})" if step.get_duration_str() else ""
                                project_branch.add(
                                    f"[{step_color}]{step_symbol} {step.name}{duration}[/{step_color}]"
                                )
                        
                        # Show latest message if any
                        latest_msg = project.get_latest_message()
                        if latest_msg:
                            msg_color = {
                                MessageLevel.INFO: "white",
                                MessageLevel.WARNING: "yellow",
                                MessageLevel.ERROR: "red",
                                MessageLevel.CRITICAL: "bold orange3"
                            }.get(latest_msg.level, "white")
                            msg_text = latest_msg.message
                            if len(msg_text) > 60:
                                msg_text = msg_text[:57] + "..."
                            project_branch.add(f"[{msg_color}]├─ {msg_text}[/{msg_color}]")
                        
                        # Show log file path for running projects
                        if project.log_file_path:
                            project_branch.add(f"[dim cyan]└─ Log: {project.log_file_path}[/dim cyan]")
                    else:
                        # Simple entry for other states
                        text = project_text
                        if project.message:
                            text += f" [dim]- {project.message}[/dim]"
                        
                        # For failed/completed projects with issues, add a sub-branch with log info
                        if (state == StepState.FAILED or 
                            (state == StepState.COMPLETED and msg_summary)):
                            project_branch = branch.add(text)
                            
                            # Add log file path if available
                            if project.log_file_path:
                                project_branch.add(f"[dim cyan]└─ Log: {project.log_file_path}[/dim cyan]")
                        else:
                            branch.add(text)
            
            return Panel(
                tree,
                border_style="blue",
                box=box.ROUNDED,
                subtitle_align="right"
            )