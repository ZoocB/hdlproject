"""Publish handler - publishes projects to CI/CD pipeline.

This handler manages git operations to trigger CI/CD builds.
"""

import hashlib
import subprocess
import uuid
from dataclasses import dataclass

import yaml

from hdlproject.handlers.base.handler import BaseHandler
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.registry import HandlerInfo, register_handler
from hdlproject.handlers.services.status_manager import StatusManager
from hdlproject.models.resolved import ResolvedProjectConfig
from hdlproject.runtime.context import (
    ExecutionContext,
    ExecutionServices,
    RuntimeEnvironment,
    SingleProjectExecution,
)
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


@dataclass
class PublishHandlerOptions:
    """Publish operation options."""

    pass


class PublishHandler(BaseHandler):
    """Handler for publishing projects to CI/CD."""

    CONFIG = OperationConfig(
        name="publish",
        tcl_mode="",  # Not used - pure git operation
        step_patterns=[],  # No Vivado output
        operation_steps=[
            "Checking Git Status",
            "Loading Project Configurations",
            "Updating Build Token",
            "Amending Commit",
            "Pushing Changes",
            "Complete",
        ],
    )

    def __init__(
        self,
        environment: RuntimeEnvironment,
        interactive: bool = False,
    ):
        super().__init__(environment, interactive)
        self.token_dir = self.environment.repository_root / ".hdlproject"
        self.token_file = self.token_dir / "build-token.yaml"
        self.project_configs: dict[str, ResolvedProjectConfig] = {}

    def configure(self, context: ExecutionContext) -> None:
        """Display publish configuration."""
        # Store resolved configs for later use
        for config in context.resolved_configs:
            self.project_configs[config.project_name] = config

        print("\n" + "=" * 50)
        print("Publish Configuration")
        print("=" * 50)
        print(f"Projects to publish: {len(context.resolved_configs)}")

        # Group by tool and version
        version_groups: dict[str, list[str]] = {}
        for name, config in self.project_configs.items():
            label = f"{config.tool} {config.tool_version}"
            if label not in version_groups:
                version_groups[label] = []
            version_groups[label].append(name)

        for label, projects in sorted(version_groups.items()):
            print(f"\n{label}:")
            for project in projects:
                print(f"  - {project}")

        print(f"\nCurrent branch: {self._get_current_branch()}")
        print(f"Repository root: {self.environment.repository_root}")
        print("=" * 50 + "\n")

    def prepare(self, context: SingleProjectExecution) -> None:
        """Prepare is not used - all work done in execute."""
        pass

    def execute_single(self, context: SingleProjectExecution) -> bool:
        """Not used - publish works on all projects at once."""
        return True

    def execute(self, projects: list[str], options: PublishHandlerOptions) -> None:
        """Override execute to handle git operations on all projects."""
        try:
            # Load projects without file or executor validation
            # (publish doesn't need to execute tools, just read project configs)
            resolved_configs = self.project_loader.load_projects(
                projects,
                check_files=False,
                check_executor=False,
            )

            # Setup token directory
            self.token_dir.mkdir(exist_ok=True)

            # Create services
            services = ExecutionServices(
                tool_executor=self.tool_executor_service,
                status_manager=None,
                compile_order_service=None,
            )

            # Create execution context
            context = ExecutionContext(
                environment=self.environment,
                resolved_configs=resolved_configs,
                handler_options=options,
                operation_config=self.CONFIG,
                services=services,
            )

            # Create status manager for git operations
            self.status_manager = StatusManager(
                operation_name=self.CONFIG.name,
                operation_steps=self.CONFIG.operation_steps,
                project_names=["git-operations"],
            )
            services.status_manager = self.status_manager

            # Start display
            self.status_manager.start()

            # Display configuration
            self.configure(context)

            # Start tracking
            self.status_manager.start_project("git-operations")

            # Check if branch is behind remote
            self.status_manager.update_step("git-operations", "Checking Git Status")
            if self._is_branch_behind_remote():
                raise RuntimeError(
                    "Your branch is behind the remote. Please pull first:\n"
                    f"  cd {self.environment.repository_root}\n"
                    f"  git pull origin {self._get_current_branch()}"
                )
            self.status_manager.update_step(
                "git-operations", "Checking Git Status", step_result="success"
            )

            # Load project configurations
            self.status_manager.update_step(
                "git-operations", "Loading Project Configurations"
            )
            self.status_manager.update_step(
                "git-operations",
                "Loading Project Configurations",
                step_result="success",
            )

            # Update build token
            self.status_manager.update_step("git-operations", "Updating Build Token")
            token = self._update_build_token(projects)
            self.status_manager.update_step(
                "git-operations", "Updating Build Token", step_result="success"
            )

            # Check if we have a local commit to amend
            has_local_commit = self._has_unpushed_commits()

            if has_local_commit:
                self.status_manager.update_step("git-operations", "Amending Commit")
                self._amend_commit()
                self.status_manager.update_step(
                    "git-operations", "Amending Commit", step_result="success"
                )
            else:
                self.status_manager.update_step("git-operations", "Amending Commit")
                self._create_commit(token)
                self.status_manager.update_step(
                    "git-operations", "Amending Commit", step_result="success"
                )

            # Push changes
            self.status_manager.update_step("git-operations", "Pushing Changes")
            self._push_changes()
            self.status_manager.update_step(
                "git-operations", "Pushing Changes", step_result="success"
            )

            # Complete
            self.status_manager.update_step(
                "git-operations", "Complete", step_result="success"
            )
            self.status_manager.complete_project("git-operations", success=True)

            print(f"\n✓ Successfully published {len(projects)} project(s)")
            print(f"  Token: {token}")
            print(f"  Branch: {self._get_current_branch()}")

        except Exception as e:
            logger.error(f"Publish failed: {e}")
            if self.status_manager:
                self.status_manager.complete_project(
                    "git-operations", success=False, message=str(e)
                )
            raise
        finally:
            if self.status_manager:
                self.status_manager.cleanup()

    def _is_branch_behind_remote(self) -> bool:
        """Check if local branch is behind remote."""
        try:
            branch = self._get_current_branch()

            subprocess.run(
                ["git", "fetch", "origin", branch],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            result = subprocess.run(
                ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            commits_behind = int(result.stdout.strip())
            if commits_behind > 0:
                logger.warning(f"Branch is {commits_behind} commit(s) behind")
                return True

            return False

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to check branch status: {e.stderr or str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _has_unpushed_commits(self) -> bool:
        """Check if there are local commits not yet pushed."""
        try:
            branch = self._get_current_branch()

            result = subprocess.run(
                ["git", "rev-list", "--count", f"origin/{branch}..HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            commits_ahead = int(result.stdout.strip())
            has_commits = commits_ahead > 0

            if has_commits:
                logger.info(f"Found {commits_ahead} local commit(s) to amend")
            else:
                logger.info("No local commits found, will create new commit")

            return has_commits

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to check unpushed commits: {e.stderr or str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _get_current_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to get current branch: {e.stderr or str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _get_commit_hash(self) -> str:
        """Get current commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to get commit hash: {e.stderr or str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _generate_token(self, projects: list[str]) -> str:
        """Generate unique build token."""
        commit_hash = self._get_commit_hash()
        unique_id = str(uuid.uuid4())
        project_hash = hashlib.md5(",".join(sorted(projects)).encode()).hexdigest()[:8]
        return f"{commit_hash[:8]}-{project_hash}-{unique_id[:8]}"

    def _update_build_token(self, projects: list[str]) -> str:
        """Update build token file."""
        token = self._generate_token(projects)

        # Build project data with Vivado versions
        project_data = {}
        for project in projects:
            if project in self.project_configs:
                config = self.project_configs[project]
                project_data[project] = {
                    "tool": config.tool,
                    "tool_version": config.tool_version,
                }

        build_data = {"token": token, "projects": project_data}

        with open(self.token_file, "w") as f:
            yaml.dump(build_data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Updated build token: {token}")
        return token

    def _amend_commit(self) -> None:
        """Amend current commit with build token."""
        try:
            relative_path = self.token_file.relative_to(
                self.environment.repository_root
            )

            subprocess.run(
                ["git", "add", str(relative_path)],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            subprocess.run(
                ["git", "commit", "--amend", "--no-edit"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            logger.info("Amended commit with build token")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to amend commit: {e.stderr or str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _create_commit(self, token: str) -> None:
        """Create new commit with build token."""
        try:
            relative_path = self.token_file.relative_to(
                self.environment.repository_root
            )

            subprocess.run(
                ["git", "add", str(relative_path)],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            commit_message = f"publish-commit-cicd: token {token}"
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            logger.info(f"Created new commit: {commit_message}")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to create commit: {e.stderr or str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _push_changes(self) -> None:
        """Push changes to remote."""
        branch = self._get_current_branch()

        try:
            subprocess.run(
                ["git", "push", "origin", branch, "--force-with-lease"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.environment.repository_root,
            )

            logger.info(f"Pushed to {branch}")

        except subprocess.CalledProcessError as e:
            error_lines = [f"Git push to 'origin/{branch}' failed"]

            if e.stderr:
                error_lines.append(f"Git error: {e.stderr.strip()}")

            error_lines.append("\nPossible causes:")
            error_lines.append("  - Remote repository is not accessible")
            error_lines.append("  - Authentication failed")
            error_lines.append("  - Branch protection rules")

            error_msg = "\n".join(error_lines)
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e


# Register handler
register_handler(
    HandlerInfo(
        name="publish",
        handler_class=PublishHandler,
        options_class=PublishHandlerOptions,
        description="Publish projects to CI/CD pipeline",
        menu_name="Publish to CI/CD",
        cli_arguments=[
            {"name": "projects", "nargs": "+", "help": "Project names to publish"}
        ],
        supports_multiple=True,
    )
)
