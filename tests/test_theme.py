import unittest

from sidedock.theme import resolve_colors, build_dock_qss

class ThemeContrastTests(unittest.TestCase):
    def test_dark_and_deep_dark_are_distinct(self):
        dark = resolve_colors({"mode": "dark"})
        deep = resolve_colors({"mode": "deep_dark"})
        self.assertLess(sum(deep["bg"]), sum(dark["bg"]))
        self.assertGreater(deep["alpha"], 240)
        self.assertIn("QToolTip", build_dock_qss(deep))

if __name__ == "__main__":
    unittest.main()
