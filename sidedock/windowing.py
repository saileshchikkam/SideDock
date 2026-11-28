"""Windows window placement and fullscreen checks for the edge trigger."""

import ctypes
from ctypes import wintypes

from sidedock.diagnostics import log


user32 = ctypes.WinDLL("user32", use_last_error=True)
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
WS_EX_TOPMOST = 0x08
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SW_SHOWNOACTIVATE = 4
MONITOR_DEFAULTTONULL = 0


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetShellWindow.restype = wintypes.HWND
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindowAsync.restype = wintypes.BOOL
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.IsZoomed.restype = wintypes.BOOL
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowLongW.restype = wintypes.LONG
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
user32.SetWindowPos.restype = wintypes.BOOL


def is_topmost(hwnd):
    return bool(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)


def set_no_activate(hwnd, enabled):
    ctypes.set_last_error(0)
    current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not current and (error := ctypes.get_last_error()):
        log.warning("GetWindowLongW failed code=%s", error)
        return
    updated = current | WS_EX_NOACTIVATE if enabled else current & ~WS_EX_NOACTIVATE
    if updated == current:
        return
    ctypes.set_last_error(0)
    previous = user32.SetWindowLongW(hwnd, GWL_EXSTYLE, updated)
    if not previous and (error := ctypes.get_last_error()):
        log.warning("SetWindowLongW failed code=%s", error)


def raise_without_activation(hwnd):
    if not user32.SetWindowPos(
        hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
    ):
        log.warning("SetWindowPos failed code=%s", ctypes.get_last_error())


def is_shell_foreground(hwnd):
    """Allow edge reveal on the real Explorer desktop, not fullscreen games.

    Win+D can foreground Progman/WorkerW. Their fullscreen rectangle
    must not be mistaken for an exclusive fullscreen application.
    Match the actual shell PID to avoid trusting a spoofed class name.
    """
    shell = user32.GetShellWindow()
    if not hwnd or not shell:
        return False
    if hwnd == shell:
        return True
    classname = ctypes.create_unicode_buffer(96)
    if not user32.GetClassNameW(hwnd, classname, len(classname)):
        return False
    if classname.value not in ("Progman", "WorkerW", "Shell_TrayWnd"):
        return False
    shell_pid = wintypes.DWORD()
    foreground_pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(shell, ctypes.byref(shell_pid))
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(foreground_pid))
    return bool(shell_pid.value and shell_pid.value == foreground_pid.value)


def restore_window_without_activation(hwnd):
    """Undo an Explorer Show Desktop/minimize without taking keyboard focus."""
    if not user32.IsWindow(hwnd):
        return False
    if not user32.IsIconic(hwnd) and user32.IsWindowVisible(hwnd):
        return False
    # ShowWindowAsync's return value reports previous visibility, not success.
    user32.ShowWindowAsync(hwnd, SW_SHOWNOACTIVATE)
    log.info("recovered hidden or minimized dock")
    return True


def wake_existing_instance():
    """Let a second launch make a running dock reachable instead of a lock popup."""
    hwnd = user32.FindWindowW(None, "SideDock")
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    user32.ShowWindowAsync(hwnd, SW_SHOWNOACTIVATE)
    raise_without_activation(hwnd)
    return True


def pointer_hits_dock(hwnd):
    cursor = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(cursor)):
        return None
    hit = user32.WindowFromPoint(cursor)
    if not hit:
        return None
    return hit == hwnd or user32.GetAncestor(hit, 2) == hwnd  # GA_ROOT


def edge_available(hwnd, *, polling=False):
    """Check the input desktop and fullscreen bounds in native pixels."""
    cursor = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(cursor)):
        return False
    if polling and any(user32.GetAsyncKeyState(button) & 0x8000 for button in (1, 2, 4)):
        return False
    foreground = user32.GetForegroundWindow()
    if not foreground or foreground == hwnd or is_shell_foreground(foreground):
        return True
    style = user32.GetWindowLongW(foreground, GWL_STYLE)
    if user32.IsZoomed(foreground) and style & WS_CAPTION == WS_CAPTION:
        return True
    monitor = user32.MonitorFromPoint(cursor, MONITOR_DEFAULTTONULL)
    info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
    window = wintypes.RECT()
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    if not user32.GetWindowRect(foreground, ctypes.byref(window)):
        return True  # Foreground can close between the two calls.
    bounds = info.rcMonitor
    return not (
        window.left <= bounds.left and window.top <= bounds.top
        and window.right >= bounds.right and window.bottom >= bounds.bottom
    )
