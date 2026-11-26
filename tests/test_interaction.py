import unittest

from sidedock.interaction import select_paste_target, shortcut_keys


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
