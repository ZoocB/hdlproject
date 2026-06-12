# Architecture

`hdlproject` separates *what to do* (resolve config, run Vivado, interpret its
output) from *how to present it*. The front-end is a lightweight keyboard-driven
menu; progress during a run is rendered separately through a small interface, so
the engine never depends on the UI and a different front-end could be added later
without touching it.

## The ProgressSink seam

```
            ┌──────────────────────────────────────────────┐
            │  Execution core (front-end agnostic)          │
            │  Application → BaseHandler → ToolExecutor      │
            │  → VivadoOutputProcessor → StepTracker         │
            └───────────────────────┬──────────────────────┘
                                    │ emits progress via
                                    ▼
                          ProgressSink (Protocol)
                                    │
                                    ▼
                             RichLiveSink
                       (live Rich tree during a run)
```

[`ProgressSink`](../src/hdlproject/core/progress.py) is a structural `Protocol`:
`start_project`, `update_project_step`, `complete_project`, `set_extra_info`,
`set_project_context_name`, `set_build_artefacts_path`, and `process_output`.
The core calls these as a run proceeds; it never imports Rich.

[`RichLiveSink`](../src/hdlproject/utils/rich_sink.py) is the only implementation
today: it tracks per-project [`ProjectStatus`](../src/hdlproject/core/progress_model.py)
and renders it as a Rich `Live` tree refreshed by a daemon thread, with a final
summary on stop. [`StatusManager`](../src/hdlproject/handlers/services/status_manager.py)
builds one for interactive TTYs, or none when output is silenced. The `Protocol`
keeps the seam open for an alternative front-end, but no speculative scaffolding
is kept for one.

The user-facing interaction is the keyboard menu
([ui/menu.py](../src/hdlproject/ui/menu.py)) — project selection and operation
prompts via [InquirerPy](https://github.com/kazhala/InquirerPy) — which calls
`Application.execute_handler`; the live Rich status then renders during the run.

## Tool backends

Everything tool-specific about *running* a project lives behind
[`ToolBackend`](../src/hdlproject/backends/base.py): how its scripts are generated
and how its executable is invoked.

```
ToolExecutorService
   │  get_tool_backend(resolved_config.tool)
   ▼
ToolBackend (ABC)            ← registry, keyed by tool name
   └─ VivadoBackend          ← the only backend today
        ├─ generate_scripts() → wraps TclGenerator (tcl/vivado/templates + static)
        ├─ batch_invocation() → ["-mode","batch","-notrace","-source", <entry>]
        └─ gui_invocation()   → ["-mode","gui","-notrace", <project>]
```

The executor is tool-agnostic: it asks the backend for the entry-point script and
the executable arguments, then handles shell/Docker wrapping, streaming,
cancellation and parsing uniformly. Template trees are already namespaced per
tool (`tcl/vivado/templates`), so adding a tool means adding a `ToolBackend`
subclass plus its own `tcl/<tool>/…` scripts and registering it — no changes to
the executor or handlers. (No other tool is implemented yet — this is just the
plug-in point.)

## Output interpretation

[`VivadoOutputProcessor`](../src/hdlproject/core/output_processor.py) is a thin
IO/threading shell: it reads stdout/stderr, timestamps each line into the log
file, parses it with
[`VivadoOutputParser`](../src/hdlproject/utils/vivado_output_parser.py), and feeds
the result to [`StepTracker`](../src/hdlproject/core/step_tracker.py).

`StepTracker` is the pure state machine — it owns the finicky rules (TCL marker
steps vs. Vivado phases, severity counting, success determination) and emits
sink calls plus a final `BuildOutcome`. It is unit-tested in isolation, and the
parser's decisions are locked by a golden snapshot, so this behaviour cannot
drift unintentionally. **Treat changes here carefully — Vivado output is
notoriously irregular.**

## Cancellation

Each run owns a [`CancellationToken`](../src/hdlproject/core/cancellation.py).
`sigint_cancels` installs a Ctrl+C handler (on the main thread) that trips the
token instead of raising. Vivado is launched in its own process group
(`start_new_session=True`); on cancellation `terminate_process_group` escalates
SIGINT → SIGTERM → SIGKILL across the whole group so no child is orphaned.

## Configuration

YAML config is parsed into Pydantic models under
[`models/`](../src/hdlproject/models/), merged with inheritance, and resolved to
an absolute-path [`ResolvedProjectConfig`](../src/hdlproject/models/resolved.py)
that is the single object passed through execution. User-authored Jinja2 (the
`artefact_name` string and `generated_sources` templates) is rendered through a
sandboxed environment to block injection.
