"""Pure policy helpers for shortcut and foreground-window handling."""


def shortcut_keys(preset):
    if preset == "alternative":
        return "ctrl+alt+v", "ctrl+shift+alt", "Ctrl+Shift+Alt"
    return "ctrl+shift+v", "ctrl+alt", "Ctrl+Alt"


def select_paste_target(foreground, search_target, own_pid):
    if not foreground:
        return None
    target = search_target if foreground[1] == own_pid else foreground
    return target if target and target[1] != own_pid else None
