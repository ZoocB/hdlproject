# handlers/publish.py
"""Publish handler - refactored with service composition"""

import subprocess
import yaml
import uuid
import hashlib
from pathlib import Path
from dataclasses import dataclass

from hdlproject.handlers.base.handler import BaseHandler
from hdlproject.handlers.base.context import ExecutionContext, SingleProjectContext
from hdlproject.handlers.base.operation_config import OperationConfig
from hdlproject.handlers.registry import HandlerInfo, register_handler
from hdlproject.utils.vivado_output_parser import StepPattern
from hdlproject.utils.logging_manager import get_logger

logger = get_logger(__name__)


@dataclass
class PublishOptions:
    """Publish operation options"""

    pass


class PublishHandler(BaseHandler):
    """Handler for publishing projects to CI/CD"""

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

    def __init__(self, environment: dict, interactive: bool = False):
        super().__init__(environment, interactive)
        self.repository_root = Path(environment["repository_root"])
        self.jenkins_dir = self.repository_root / ".jenkins"
        self.token_file = self.jenkins_dir / "build-token.yaml"
        self.project_configs = {}

    def configure(self, context: ExecutionContext) -> None:
        """Display publish configuration"""
        # Load all project configs to get Vivado versions
        for proj_ctx in context.projects:
            self.project_configs[proj_ctx.config.name] = proj_ctx.config

        print("\n" + "=" * 50)
        print("Publish Configuration")
        print("=" * 50)
        print(f"Projects to publish: {len(context.projects)}")

        # Group by Vivado version
        version_groups = {}
        for name, config in self.project_configs.items():
            version = config.vivado_version.full_version
            if version not in version_groups:
                version_groups[version] = []
            version_groups[version].append(name)

        for version, projects in sorted(version_groups.items()):
            print(f"\nVivado {version}:")
            for project in projects:
                print(f"  - {project}")

        print(f"\nCurrent branch: {self._get_current_branch()}")
        print(f"Repository root: {self.repository_root}")
        print("=" * 50 + "\n")

    def prepare(self, context: SingleProjectContext) -> None:
        """Prepare is not used - all work done in execute"""
        pass

    def execute_single(self, context: SingleProjectContext) -> bool:
        """Not used - publish works on all projects at once"""
        return True

    def execute(self, projects: list[str], options: PublishOptions) -> None:
        """Override execute to handle git operations on all projects"""
        try:
            # Load projects without Vivado validation (publish doesn't need Vivado)
            project_contexts = self.project_loader.load_projects(projects, self.CONFIG.name, check_vivado=False)

            # Setup jenkins directory
            self.jenkins_dir.mkdir(exist_ok=True)

            # Create execution context
            context = ExecutionContext(
                projects=project_contexts,
                options=options,
                operation_config=self.CONFIG,
                environment=self.environment,
                vivado_executor=self.vivado_executor,
                status_manager=None,  # Created below
                compile_order_service=self.compile_order_service,
            )

            # Create status manager for git operations
            self.status_manager = StatusManager(
                operation_name=self.CONFIG.name, operation_steps=self.CONFIG.operation_steps, project_names=["git-operations"]
            )
            context.status_manager = self.status_manager

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
                    "Your branch is behind the remote. Please pull the latest changes first:\n"
                    f"  cd {self.repository_root}\n"
                    f"  git pull origin {self._get_current_branch()}"
                )

            # Update build token
            self.status_manager.update_step("git-operations", "Updating Build Token")
            token = self._update_build_token(projects)

            # Check if we have a local commit to amend, or need to create new commit
            has_local_commit = self._has_unpushed_commits()

            if has_local_commit:
                # Amend existing commit
                self.status_manager.update_step("git-operations", "Amending Commit")
                self._amend_commit()
            else:
                # Create new commit with token
                self.status_manager.update_step("git-operations", "Creating Commit")
                self._create_commit(token)

            # Push changes
            self.status_manager.update_step("git-operations", "Pushing Changes")
            self._push_changes()

            # Complete
            self.status_manager.update_step("git-operations", "Complete")
            self.status_manager.complete_project("git-operations", success=True)

            print(f"\nÃ¢Å“â€œ Successfully published {len(projects)} project(s)")
            print(f"  Token: {token}")
            print(f"  Branch: {self._get_current_branch()}")

        except Exception as e:
            logger.error(f"Publish failed: {e}")
            if self.status_manager:
                self.status_manager.complete_project("git-operations", success=False, message=str(e))
            raise
        finally:
            if self.status_manager:
                self.status_manager.cleanup()

    def _is_branch_behind_remote(self) -> bool:
        """Check if local branch is behind remote"""
        try:
            branch = self._get_current_branch()

            # Fetch latest from remote
            subprocess.run(["git", "fetch", "origin", branch], capture_output=True, text=True, check=True, cwd=self.repository_root)

            # Check if behind
            result = subprocess.run(
                ["git", "rev-list", "--count", f"HEAD..origin/{branch}"], capture_output=True, text=True, check=True, cwd=self.repository_root
            )

            commits_behind = int(result.stdout.strip())
            if commits_behind > 0:
                logger.warning(f"Branch is {commits_behind} commit(s) behind origin/{branch}")
                return True

            return False

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to check if branch is behind: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _has_unpushed_commits(self) -> bool:
        """Check if there are local commits not yet pushed to remote"""
        try:
            branch = self._get_current_branch()

            # Check if ahead of remote
            result = subprocess.run(
                ["git", "rev-list", "--count", f"origin/{branch}..HEAD"], capture_output=True, text=True, check=True, cwd=self.repository_root
            )

            commits_ahead = int(result.stdout.strip())
            has_commits = commits_ahead > 0

            if has_commits:
                logger.info(f"Found {commits_ahead} local commit(s) to amend")
            else:
                logger.info("No local commits found, will create new commit")

            return has_commits

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to check unpushed commits: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _get_current_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True, cwd=self.repository_root
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to get current branch: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _get_commit_hash(self) -> str:
        """Get current commit hash"""
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=self.repository_root)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to get commit hash: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _generate_token(self, projects: list[str]) -> str:
        """Generate unique build token"""
        commit_hash = self._get_commit_hash()
        unique_id = str(uuid.uuid4())
        project_hash = hashlib.md5(",".join(sorted(projects)).encode()).hexdigest()[:8]
        return f"{commit_hash[:8]}-{project_hash}-{unique_id[:8]}"

    def _update_build_token(self, projects: list[str]) -> str:
        """Update build token file"""
        token = self._generate_token(projects)

        # Build project data with Vivado versions
        project_data = {}
        for project in projects:
            if project in self.project_configs:
                config = self.project_configs[project]
                project_data[project] = {"vivado_version": config.vivado_version.full_version}

        # Write token file
        build_data = {"token": token, "projects": project_data}

        with open(self.token_file, "w") as f:
            yaml.dump(build_data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Updated build token: {token}")
        return token

    def _amend_commit(self) -> None:
        """Amend current commit with build token"""
        try:
            relative_path = self.token_file.relative_to(self.repository_root)

            # Stage the token file
            result = subprocess.run(["git", "add", str(relative_path)], capture_output=True, text=True, check=True, cwd=self.repository_root)

            # Amend commit
            result = subprocess.run(["git", "commit", "--amend", "--no-edit"], capture_output=True, text=True, check=True, cwd=self.repository_root)

            logger.info("Amended commit with build token")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to amend commit: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _create_commit(self, token: str) -> None:
        """Create new commit with build token"""
        try:
            relative_path = self.token_file.relative_to(self.repository_root)

            # Stage the token file
            result = subprocess.run(["git", "add", str(relative_path)], capture_output=True, text=True, check=True, cwd=self.repository_root)

            # Create commit with token in message
            commit_message = f"publish-commit-cicd: token {token}"
            result = subprocess.run(["git", "commit", "-m", commit_message], capture_output=True, text=True, check=True, cwd=self.repository_root)

            logger.info(f"Created new commit: {commit_message}")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to create commit: {e.stderr if e.stderr else str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _push_changes(self) -> None:
        """Push changes to remote"""
        branch = self._get_current_branch()

        try:
            result = subprocess.run(["git", "push", "origin", branch], capture_output=True, text=True, check=True, cwd=self.repository_root)

            logger.info(f"Pushed to {branch}")

        except subprocess.CalledProcessError as e:
            # Construct detailed error message
            error_lines = []
            error_lines.append(f"Git push to 'origin/{branch}' failed")

            if e.stderr:
                error_lines.append("Git error output:")
                error_lines.append(e.stderr.strip())

            if e.stdout:
                error_lines.append("Git standard output:")
                error_lines.append(e.stdout.strip())

            # Add helpful suggestions
            error_lines.append("\nPossible causes:")
            error_lines.append("  - Remote repository is not accessible")
            error_lines.append("  - Authentication failed (check credentials/SSH keys)")
            error_lines.append("  - Branch protection rules preventing push")
            error_lines.append("  - Network connectivity issues")
            error_lines.append(f"  - Remote 'origin' not configured correctly")
            error_lines.append("\nTry running manually to see full error:")
            error_lines.append(f"  cd {self.repository_root}")
            error_lines.append(f"  git push origin {branch}")

            error_msg = "\n".join(error_lines)
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e


# Import StatusManager here to avoid circular import
from hdlproject.handlers.services.status_manager import StatusManager


# Register handler
register_handler(
    HandlerInfo(
        name="publish",
        handler_class=PublishHandler,
        options_class=PublishOptions,
        description="Publish projects to CI/CD pipeline",
        menu_name="Publish to CI/CD",
        cli_arguments=[{"name": "projects", "nargs": "+", "help": "Project names to publish"}],
        supports_multiple=True,
    )
)