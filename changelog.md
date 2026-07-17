# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `project_information.default_library` in `hdlproject_project_config.yaml`
  sets the project's default HDL compilation library (Vivado's `default_lib`
  project property). Optional; defaults to `work`, preserving existing
  behaviour for configs that omit it.

### Fixed

- `environment_setup` scripts wrote their variables into the process-wide
  environment at config-load time, leaking one project's variables into
  other projects and racing during parallel builds. Captured variables now
  live on `ResolvedProjectConfig.environment`, scoped to the owning
  project: `${VAR}` expansion in that project's own config still sees them
  (via Pydantic validation context), and tool/compile-order subprocesses
  receive them through their spawn environment. `os.environ` is never
  modified.
- Importing hdlproject destroyed the host application's logging
  configuration (the root logger's handlers were cleared and replaced at
  import time). Console handling now attaches lazily to the `hdlproject`
  package logger; importing the package configures nothing. The CLI's
  console output and the application log file are unchanged — the file
  still captures both hdlproject's own records and third-party library
  output.
- Opening the tool GUI through a shell-wrapped executor (heredoc mode)
  would have crashed writing text to a bytes stdin pipe; the GUI launch
  now uses text mode like the batch path.

### Changed (internal API)

- `config/config_resolver.py` renamed to `config/yaml_loader.py`
  (matching its `YAMLConfigLoader` class), and `config/resolver.py` to
  `config/project_resolver.py` with `ConfigResolver` renamed to
  `ProjectConfigResolver`.
- Project loggers moved from the `project.*` to the
  `hdlproject.project.*` namespace.
- mypy is now enforcing (`check_untyped_defs`, `warn_unused_ignores`);
  the package type-checks clean, with annotations corrected where they
  misdescribed runtime types (notably the InquirerPy style helper).

### Fixed (initial review pass)

- `--compile-order-format` had an argparse default of `"json"`, which made the
  global config's `compile_order_format` setting unreachable. The CLI default
  is now `None`, restoring the documented precedence: CLI flag → global
  config → `"json"`. Effective behaviour is unchanged unless a config file
  sets the key.
- Diamond inheritance in YAML configs (two parents sharing a common base)
  merged the shared base once per branch, duplicating list entries and
  raising spurious "Duplicate definition" errors for scalars. A shared
  ancestor is now merged exactly once (first occurrence wins); genuine
  circular inheritance is still rejected.
- Handler-loading failures during CLI parser construction were silently
  swallowed, leaving a parser with no subcommands and a misleading
  "invalid choice" error. Failures now print a warning to stderr while
  keeping `--help` usable.
- `hdlproject` no longer writes `safe.directory` entries into the user's
  global git configuration on every run. If git reports dubious ownership,
  an actionable error explains the one-time fix instead.
- Package version was inconsistent (`1.0.0` in `hdlproject.__version__`,
  `0.2.0` in `pyproject.toml`). The version is now single-sourced from
  `hdlproject.__version__` (currently `0.2.0`) via setuptools dynamic
  metadata.
- README's global configuration example used keys that do not exist in the
  schema (`compile_order_script_format`, `default_cores_per_project`); the
  example now matches `GlobalConfiguration` and includes a working `tools:`
  section. Stale `--project-dir` help text referencing
  `hdlproject-config.json` corrected to `hdlproject_global_config.yaml`.

### Added

- `py.typed` marker so type checkers consume the package's annotations
  (PEP 561).
- Project metadata in `pyproject.toml`: keywords, trove classifiers, and
  homepage URL.
- Regression tests for diamond and circular YAML inheritance.
- `.pre-commit-config.yaml` and `scripts/` are now tracked (they were
  gitignored), so fresh clones can install pre-commit hooks and regenerate
  the YAML configuration guide.

### Changed

- Application startup loads and validates the global configuration once
  instead of three times.
- Exceptions raised while handling lower-level errors now chain the original
  cause (`raise ... from e`, PEP 3134) across the config and application
  layers, so tracebacks show the root failure.
- Handler options silently dropped during dispatch are now logged at debug
  level.
- Removed dead constants (`KNOWN_BUILD_OPERATIONS`, `HDLPROJECT_DIR_BASE`,
  `DEFAULT_MAX_PARALLEL_BUILDS`, `DEFAULT_CORES_PER_PROJECT`,
  `VIVADO_TOOL_NAME`, `XSIM_TOOL_NAME`), one of which contradicted the real
  operation list in `models/resolved.py`.
- `src/` is now clean under `ruff check` (35 line-length violations fixed);
  `docs/yaml-configuration-guide.md` regenerated to match the models.
- Runtime output directories (`bin/`, `.hdlproject-*/`, `venv/`) are now
  gitignored.

## [0.2.0] - 2026-06-12

- Textual dashboard refactor, YAML config support, `.hdlproject` token
  directory, and alignment with the hdldepends refactor (pre-changelog
  history; see git log).
