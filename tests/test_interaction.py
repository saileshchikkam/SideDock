import unittest

from sidedock.interaction import select_paste_target, shortcut_keys, CopyBurst


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

    def test_multiple_copies_show_only_previous_two_after_native_paste(self):
        burst = CopyBurst()
        a = {"type": "text", "content": "A"}
        b = {"type": "text", "content": "B"}
        c = {"type": "text", "content": "C"}
        burst.record(a, 100)
        burst.record(b, 107)
        burst.record(c, 113)
        # Native Ctrl+V already pasted C; only B and A remain.
        self.assertEqual(burst.consume_remaining(114), [(2, b), (3, a)])
        self.assertEqual(burst.consume_remaining(115), [])
        self.assertEqual(burst.items, [])

    def test_single_copy_never_triggers_popup_even_with_old_history(self):
        # A new application session has NO active burst, even though disk
        # history might contain years of saved copies.
        burst = CopyBurst()
        self.assertEqual(burst.consume_remaining(200), [])
        burst.record({"type": "text", "content": "A"}, 200)
        self.assertEqual(burst.consume_remaining(201), [])
        self.assertEqual(burst.consume_remaining(202), [])

    def test_two_rapid_copies_show_only_the_older_one(self):
        burst = CopyBurst()
        a = {"type": "text", "content": "A"}
        b = {"type": "text", "content": "B"}
        burst.record(a, 100)
        burst.record(b, 106)
        self.assertEqual(burst.consume_remaining(110), [(2, a)])

    def test_distant_copies_do_not_form_a_burst(self):
        burst = CopyBurst()
        burst.record({"type": "text", "content": "A"}, 10)
        burst.record({"type": "text", "content": "B"}, 35)
        self.assertEqual(burst.consume_remaining(36), [])
        burst.record({"type": "text", "content": "C"}, 37)
        self.assertEqual(len(burst.consume_remaining(38)), 1)

    def test_old_burst_expires_before_ctrl_v(self):
        burst = CopyBurst()
        burst.record({"type": "text", "content": "A"}, 1)
        burst.record({"type": "text", "content": "B"}, 5)
        self.assertEqual(burst.consume_remaining(51), [])
        self.assertEqual(burst.items, [])

    def test_burst_resets_after_paste_for_next_copy_sequence(self):
        burst = CopyBurst()
        burst.record({"type": "text", "content": "A"}, 1)
        burst.record({"type": "text", "content": "B"}, 2)
        self.assertEqual(len(burst.consume_remaining(3)), 1)
        burst.record({"type": "text", "content": "C"}, 4)
        self.assertEqual(burst.consume_remaining(5), [])  # single fresh copy

    def test_notes_and_ocr_drafts_are_not_copy_events(self):
        burst = CopyBurst()
        burst.record({"type": "text", "content": "A"}, 1)
        burst.record({"type": "note", "content": "A note"}, 2)
        burst.record({"type": "text", "source": "ocr", "content": "OCR draft"}, 3)
        self.assertEqual(burst.consume_remaining(4), [])

    def test_delete_or_pause_cancels_earlier_popup_candidates(self):
        burst = CopyBurst()
        a = {"type": "text", "content": "A"}
        b = {"type": "text", "content": "B"}
        burst.record(a, 1)
        burst.record(b, 2)
        burst.forget(a)
        self.assertEqual(burst.consume_remaining(3), [])
        burst.record(a, 4)
        burst.record(b, 5)
        burst.clear()
        self.assertEqual(burst.consume_remaining(6), [])

    def test_burst_keeps_only_last_three_of_many_quick_copies(self):
        burst = CopyBurst()
        copies = [{"type": "text", "content": chr(65+i)} for i in range(5)]
        for i, item in enumerate(copies):
            burst.record(item, 10+i)
        self.assertEqual(burst.consume_remaining(16), [(2, copies[3]), (3, copies[2])])

    def test_copying_after_monotonic_clock_reset_starts_fresh_session(self):
        burst = CopyBurst()
        burst.record({"type": "text", "content": "A"}, 300)
        burst.record({"type": "text", "content": "B"}, 1)
        self.assertEqual(burst.consume_remaining(2), [])
