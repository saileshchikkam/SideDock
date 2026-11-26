"""Per-user Windows startup registration, shared by packaged and Python installs."""
import os
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SideDock"


def startup_command(executable, frozen=False, pythonw_exists=False):
    executable = Path(executable)
    if frozen:
        return subprocess.list2cmdline([str(executable)])
    if pythonw_exists:
        executable = executable.with_name("pythonw.exe")
    return subprocess.list2cmdline([str(executable), "-m", "sidedock"])


def legacy_launcher():
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "SideDock.vbs"


def is_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value) or legacy_launcher().exists()
    except FileNotFoundError:
        return legacy_launcher().exists()


def set_enabled(enabled):
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            executable = Path(sys.executable)
            command = startup_command(executable, getattr(sys, "frozen", False), executable.with_name("pythonw.exe").exists())
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
    # Explicit user toggle also removes SideDock's legacy startup entry,
    # preventing two launches after upgrading.
    legacy_launcher().unlink(missing_ok=True)
