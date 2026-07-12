#!/usr/bin/env python3
"""Pre-commit hook to regenerate YAML configuration documentation.

This hook runs the documentation generator and stages any changes.
Install with: pre-commit install

Or manually add to .git/hooks/pre-commit
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    # Find repo root (where .git lives)
    repo_root = Path(__file__).parent.parent
    if not (repo_root / ".git").exists():
        repo_root = Path.cwd()

    script_path = repo_root / "scripts" / "generate_docs.py"
    output_path = repo_root / "docs" / "yaml-configuration-guide.md"

    if not script_path.exists():
        print(f"Warning: {script_path} not found, skipping docs generation")
        return 0

    # Run the generator from repo root
    print("Regenerating YAML configuration documentation...")
    result = subprocess.run(
        [sys.executable, str(script_path), "--output", str(output_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(repo_root / "src")},
    )

    if result.returncode != 0:
        print(f"Error generating documentation:\n{result.stderr}")
        return 1

    print(result.stdout.strip())

    # Stage the generated file if it changed
    if output_path.exists():
        subprocess.run(["git", "add", str(output_path)], cwd=repo_root, check=True)
        print(f"Staged {output_path.relative_to(repo_root)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
