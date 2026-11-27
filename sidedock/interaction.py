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


# Copying several items in quick succession is one deliberate paste batch.
# Old saved history must NEVER trigger the automatic Ctrl+V popup.
COPY_BURST_GAP_SECONDS = 20.0
COPY_BURST_PASTE_GRACE_SECONDS = 45.0


class CopyBurst:
    """One-shot sequence of recently copied items, newest first.

    A sequence only stays together when adjacent copies are at most 20s
    apart. Ctrl+V must arrive within 45s of the last copy. The first native
    Ctrl+V already pastes the newest clipboard item, so show ONLY the
    earlier one or two copies in numbered slots 2 and 3.
    """

    def __init__(self, gap_seconds=COPY_BURST_GAP_SECONDS,
                 grace_seconds=COPY_BURST_PASTE_GRACE_SECONDS):
        self.gap_seconds = gap_seconds
        self.grace_seconds = grace_seconds
        self.items = []
        self.last_copy_at = None

    def clear(self):
        self.items.clear()
        self.last_copy_at = None

    def record(self, item, now):
        # Notes and local OCR review are not independent Ctrl+C events.
        if item.get("type") not in ("text", "file", "image") or item.get("source") == "ocr":
            return
        if (self.last_copy_at is None or now < self.last_copy_at
                or now - self.last_copy_at > self.gap_seconds):
            self.clear()
        self.items.insert(0, item)
        del self.items[3:]
        self.last_copy_at = now

    def forget(self, item):
        self.items[:] = [entry for entry in self.items if entry is not item]
        if not self.items:
            self.last_copy_at = None

    def consume_remaining(self, now):
        # This is triggered once after the user presses ordinary Ctrl+V.
        # Never replace, suppress, or replay that native paste.
        if (self.last_copy_at is None or now < self.last_copy_at
                or now - self.last_copy_at > self.grace_seconds
                or len(self.items) < 2):
            self.clear()
            return []
        remaining = list(enumerate(self.items[1:3], start=2))
        self.clear()  # no reappearance without a NEW multiple-copy sequence
        return remaining
