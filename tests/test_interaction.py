import unittest

from sidedock.interaction import select_paste_target, shortcut_keys, recent_copy_slots


class InteractionTests(unittest.TestCase):
    def test_foreground_wins_over_old_search(self):
        self.assertEqual(select_paste_target((1, 2, 3), (4, 5, 6), 99), (1, 2, 3))

    def test_search_restores_only_external_target(self):
        self.assertEqual(select_paste_target((1, 99, 3), (4, 5, 6), 99), (4, 5, 6))
        self.assertIsNone(select_paste_target((1, 99, 3), (4, 99, 6), 99))
        self.assertIsNone(select_paste_target((1, 99, 3), None, 99))
        self.assertIsNone(select_paste_target(None, (4, 5, 6), 99))

    def test_presets_and_fallback(self):
        self.assertEqual(shortcut_keys(None)[0], "ctrl+shift+v")
        self.assertEqual(shortcut_keys("alternative")[0], "ctrl+alt+v")
        self.assertEqual(shortcut_keys("invalid"), shortcut_keys("classic"))

    def test_ctrl_v_shows_three_saved_copies_after_restart(self):
        history = [
            {"type": "text", "content": "third copied"},
            {"type": "image", "path": "recent-image.png"},
            {"type": "file", "name": "notes.pdf", "path": "notes.pdf"},
        ]
        self.assertEqual(recent_copy_slots(history), list(enumerate(history, 1)))
        # Repeated normal paste must not consume or mutate the history.
        self.assertEqual(recent_copy_slots(history), list(enumerate(history, 1)))
        self.assertEqual(len(history), 3)

    def test_ctrl_v_excludes_notes_and_uncopied_ocr_drafts(self):
        history = [
            {"type": "note", "content": "manual note"},
            {"type": "text", "source": "ocr", "content": "extracted"},
            {"type": "text", "content": "latest copy"},
            {"type": "image", "path": "previous.png"},
            {"type": "file", "name": "older.txt"},
            {"type": "text", "content": "too old"},
        ]
        self.assertEqual(recent_copy_slots(history),
                         [(1, history[2]), (2, history[3]), (3, history[4])])

    def test_ctrl_v_keeps_native_paste_when_history_is_too_short(self):
        self.assertEqual(recent_copy_slots([]), [])
        self.assertEqual(recent_copy_slots([{"type": "text", "content": "only copy"}]), [])
        self.assertEqual(recent_copy_slots([{"type": "note", "content": "note"},
                                            {"type": "text", "content": "only copy"}]), [])

    def test_ctrl_v_ignores_malformed_history_records(self):
        history = [None, "corrupted", {"type": "text", "content": "one"},
                   {"type": "text", "content": "two"}]
        self.assertEqual(recent_copy_slots(history), [(1, history[2]), (2, history[3])])
