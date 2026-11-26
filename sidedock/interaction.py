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


def recent_copy_slots(history):
    """Build the persistent recent-copies popup without mutating the history.

    SideDock's former transient rapid-copy buffer was consumed after one
    Ctrl+V and lost at every restart. Only genuine copied cards appear here.
    """
    copies = []
    for item in history:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in ("text", "image", "file"):
            continue
        if item.get("source") == "ocr":
            continue
        copies.append(item)
        if len(copies) == 3:
            break
    return list(enumerate(copies, start=1)) if len(copies) >= 2 else []
