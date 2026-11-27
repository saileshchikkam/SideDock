"""Local lifecycle diagnostics. Log only operational metadata."""

import ctypes
import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import sys
import threading

from PySide6.QtCore import qInstallMessageHandler


log = logging.getLogger("sidedock.diagnostics")


def start_diagnostics(directory, version):
    try:
        handler = RotatingFileHandler(
            directory / "sidedock.log", maxBytes=256 * 1024, backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        return None

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

    def log_exception(kind, error_type, traceback):
        # Exception messages and source snippets can contain user data.
        frames = []
        while traceback is not None:
            code = traceback.tb_frame.f_code
            frames.append(f"{code.co_name}:{traceback.tb_lineno}")
            traceback = traceback.tb_next
        log.error("%s type=%s stack=%s", kind, error_type.__name__, " > ".join(frames))

    old_sys_hook = sys.excepthook
    old_thread_hook = threading.excepthook
    sys.excepthook = lambda kind, _error, tb: log_exception("uncaught", kind, tb)
    threading.excepthook = lambda args: log_exception(
        "thread-uncaught", args.exc_type, args.exc_traceback
    )

    def qt_message(kind, _context, _message):
        # Qt warnings can contain filenames or clipboard provider data.
        log.warning("qt message type=%s", kind.name)

    old_qt_hook = qInstallMessageHandler(qt_message)
    fatal_log = None
    try:
        latest = directory / "sidedock-fatal.log"
        if latest.exists() and latest.stat().st_size:
            latest.replace(directory / "sidedock-fatal.previous.log")
        fatal_log = latest.open("wb")
        faulthandler.enable(file=fatal_log, all_threads=False)
    except OSError:
        log.warning("native fault logging unavailable")

    log.info("startup version=%s pid=%s", version, ctypes.windll.kernel32.GetCurrentProcessId())

    def finish(exit_code):
        log.info("shutdown exit_code=%s", exit_code)
        qInstallMessageHandler(old_qt_hook)
        sys.excepthook = old_sys_hook
        threading.excepthook = old_thread_hook
        if fatal_log is not None:
            faulthandler.disable()
            fatal_log.close()
        log.removeHandler(handler)
        handler.close()

    return finish
