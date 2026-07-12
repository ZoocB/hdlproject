"""Library-safety tests for hdlproject.utils.logging_manager.

hdlproject is sometimes imported as a library by a host application. Importing
any hdlproject module (or calling get_logger) must never mutate the root
logger's handlers - only an explicit CLI action (set_verbosity /
setup_application_log) may do that, and even then it must only touch the
"hdlproject" logger and root respectively, never clobber existing root
handlers.
"""

import importlib
import logging

import pytest

from hdlproject.utils.logging_manager import LogLevel, get_logger, set_verbosity


def _root_handlers_snapshot():
    return list(logging.getLogger().handlers)


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Snapshot and restore root + "hdlproject" logger state around each test."""
    root = logging.getLogger()
    package_logger = logging.getLogger("hdlproject")

    root_handlers_before = list(root.handlers)
    root_level_before = root.level
    package_handlers_before = list(package_logger.handlers)
    package_propagate_before = package_logger.propagate
    package_level_before = package_logger.level

    yield

    for handler in root.handlers:
        if handler not in root_handlers_before:
            handler.close()
    root.handlers[:] = root_handlers_before
    root.setLevel(root_level_before)

    for handler in package_logger.handlers:
        if handler not in package_handlers_before:
            handler.close()
    package_logger.handlers[:] = package_handlers_before
    package_logger.propagate = package_propagate_before
    package_logger.setLevel(package_level_before)

    # Reset the manager's cached handler references so later tests (and the
    # manager singleton) don't hold stale handlers we just closed above.
    import hdlproject.utils.logging_manager as logging_manager

    logging_manager._manager._console_handler = None
    logging_manager._manager._app_file_handler = None


def test_import_does_not_touch_root_handlers():
    """Importing hdlproject modules must not add/remove root handlers."""
    before = _root_handlers_snapshot()

    import hdlproject.config.loader  # noqa: F401
    import hdlproject.handlers.registry  # noqa: F401

    after = _root_handlers_snapshot()
    assert after == before


def test_logging_manager_reload_does_not_touch_root_handlers():
    """Re-importing logging_manager (simulating a fresh module load) must not
    touch root - the module-level singleton build is side-effect free.

    reload() replaces the module's classes (LogLevel, LoggingManager) with
    new objects, which breaks identity for anything elsewhere that already
    holds a reference to the pre-reload classes (e.g. this test file's own
    top-level import). We snapshot and restore the module's namespace so the
    reload's effects don't leak into other tests.
    """
    before = _root_handlers_snapshot()

    import hdlproject.utils.logging_manager as logging_manager

    original_namespace = dict(vars(logging_manager))
    try:
        importlib.reload(logging_manager)
        after = _root_handlers_snapshot()
        assert after == before
    finally:
        vars(logging_manager).clear()
        vars(logging_manager).update(original_namespace)


def test_get_logger_alone_does_not_touch_root_handlers():
    before = _root_handlers_snapshot()

    logger = get_logger("hdlproject.some_module")
    logger.debug("no handlers configured yet")

    after = _root_handlers_snapshot()
    assert after == before


def test_set_verbosity_attaches_single_console_handler_to_package_logger():
    root_before = _root_handlers_snapshot()

    set_verbosity(LogLevel.NORMAL)

    package_logger = logging.getLogger("hdlproject")
    stream_handlers = [
        h for h in package_logger.handlers if isinstance(h, logging.StreamHandler)
    ]
    assert len(stream_handlers) == 1
    assert package_logger.propagate is False

    root_after = _root_handlers_snapshot()
    assert root_after == root_before


def test_console_output_format_matches_normal_verbosity(capsys):
    set_verbosity(LogLevel.NORMAL)
    logger = get_logger("hdlproject.test")

    logger.warning("hello")

    captured = capsys.readouterr()
    assert captured.out == "hello\n"


def test_project_loggers_are_namespaced_under_hdlproject(tmp_path):
    import hdlproject.utils.logging_manager as logging_manager
    from hdlproject.utils.logging_manager import get_project_logger, setup_project_log

    setup_project_log("demo", tmp_path / "demo.log")
    try:
        project_logger = get_project_logger("demo")
        assert project_logger.name == "hdlproject.project.demo"
        assert project_logger.propagate is False
    finally:
        for handler in project_logger.handlers:
            handler.close()
        project_logger.handlers.clear()
        logging_manager._manager.project_logs.pop("demo", None)
