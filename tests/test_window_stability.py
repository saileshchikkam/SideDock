import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

if sys.platform == "win32":
    from sidedock import windowing
    from sidedock.diagnostics import start_diagnostics
    from sidedock.main import SideDock, app_icon


@unittest.skipUnless(sys.platform == "win32", "SideDock uses Windows APIs")
class DockStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setWindowIcon(app_icon())

    def setUp(self):
        self.addCleanup(lambda: QTest.qWait(1))
        root = Path(self.enterContext(TemporaryDirectory()))
        data = root / "SideDockData"
        data.mkdir()
        (data / "settings.json").write_text(
            json.dumps({"capture_paused": True, "shortcuts_enabled": False}), encoding="utf-8"
        )
        self.enterContext(patch.object(Path, "home", return_value=root))
        self.enterContext(patch.object(SideDock, "setup_tray"))
        self.cursor = self.enterContext(patch("sidedock.main.QCursor"))
        self.available = self.enterContext(patch("sidedock.main.edge_available", return_value=True))
        self.dock = SideDock()
        self.dock.clip_timer.stop()
        self.cursor.pos.return_value = self.dock.monitor.availableGeometry().center()
        self.addCleanup(self.dock.deleteLater)
        self.dock.show()
        self.addCleanup(self.dock.close)

    def at_edge(self):
        self.cursor.pos.return_value = QPoint(
            max(self.dock.x_hidden, self.dock.monitor.availableGeometry().left()), self.dock.y_pos + 50
        )

    def test_timer_reveals_without_qt_enter_event(self):
        self.at_edge()
        # No mouse-move or enter event is injected into the dock.
        QTest.qWait(500)
        self.assertTrue(self.dock.is_expanded)
        self.assertFalse(self.dock.edge_watch.isActive())
        self.assertEqual(self.dock.x(), self.dock.x_shown)

    def test_edge_requires_consecutive_samples_and_respects_block(self):
        self.at_edge()
        self.dock.check_edge_hover()
        self.assertFalse(self.dock.is_expanded)
        self.available.return_value = False
        self.dock.check_edge_hover()
        self.assertFalse(self.dock.is_expanded)
        self.available.return_value = True
        self.dock.check_edge_hover()
        self.assertFalse(self.dock.is_expanded)
        self.dock.check_edge_hover()
        self.assertTrue(self.dock.is_expanded)

    def test_both_sides_keep_six_logical_pixels_at_the_work_area_edge(self):
        screen = self.dock.monitor.availableGeometry()
        for side in ("right", "left"):
            with self.subTest(side=side):
                self.dock.dock_side = side
                self.dock.on_monitor_geometry_changed()
                self.assertEqual(self.dock.geometry().intersected(screen).width(), 6)
                self.at_edge()
                self.dock.check_edge_hover()
                self.dock.check_edge_hover()
                self.assertTrue(self.dock.is_expanded)
                self.dock.collapse()
                self.dock.on_monitor_geometry_changed()

    def test_geometry_change_during_animation_settles_position_and_opacity(self):
        self.dock.expand()
        self.dock.y_pos = -99999
        self.dock.on_monitor_geometry_changed()
        self.assertEqual(self.dock.pos(), QPoint(self.dock.x_shown, self.dock.y_pos))
        self.assertTrue(self.dock.monitor.availableGeometry().contains(self.dock.geometry()))
        self.assertAlmostEqual(self.dock.windowOpacity(), 0.98, places=2)
        self.dock.collapse()
        self.dock.on_monitor_geometry_changed()
        self.assertAlmostEqual(self.dock.windowOpacity(), 0.06, places=2)

    def test_forced_collapse_requires_fresh_edge_entry_and_ocr_blocks_poll(self):
        self.at_edge()
        self.dock.expand()
        self.dock.collapse(force=True)
        self.dock.on_monitor_geometry_changed()
        self.dock.attempt_collapse()
        for _ in range(3):
            self.dock.check_edge_hover()
        self.assertFalse(self.dock.is_expanded)
        self.cursor.pos.return_value = self.dock.monitor.availableGeometry().center()
        self.dock.check_edge_hover()
        self.at_edge()
        self.dock._region_pending = True
        for _ in range(3):
            self.dock.check_edge_hover()
        self.assertFalse(self.dock.is_expanded)
        self.dock._region_pending = False
        self.dock.check_edge_hover()
        self.dock.check_edge_hover()
        self.assertTrue(self.dock.is_expanded)

    def test_notes_restore_non_activation_and_collapse_watch(self):
        self.dock.open_note_editor("disposable note")
        self.assertTrue(self.dock._editing)
        self.assertFalse(self.dock.edge_watch.isActive())
        self.dock.cancel_note_editor()
        self.assertFalse(self.dock._editing)
        self.assertTrue(self.dock.hover_watch.isActive())
        self.assertTrue(self.dock.testAttribute(Qt.WA_ShowWithoutActivating))

    def test_native_reveal_restores_topmost_without_foreground_change(self):
        if self.app.platformName() != "windows":
            self.skipTest("requires the native Windows Qt platform")
        hwnd = int(self.dock.winId())
        user32 = windowing.user32
        flags = windowing.SWP_NOSIZE | windowing.SWP_NOMOVE | windowing.SWP_NOACTIVATE
        self.assertTrue(user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, flags))
        self.assertFalse(windowing.is_topmost(hwnd))
        foreground = user32.GetForegroundWindow()
        self.dock.expand()
        self.assertTrue(windowing.is_topmost(hwnd))
        self.assertTrue(user32.GetWindowLongW(hwnd, windowing.GWL_EXSTYLE) & windowing.WS_EX_NOACTIVATE)
        self.assertEqual(user32.GetForegroundWindow(), foreground)

    def test_log_redacts_exception_details_but_keeps_stack_and_shutdown(self):
        finish = start_diagnostics(self.dock.data_dir, "test")
        self.assertIsNotNone(finish)
        try:
            try:
                raise ValueError("PRIVATE_CONTENT")
            except ValueError:
                sys.excepthook(*sys.exc_info())
            self.dock.log_heartbeat()
        finally:
            finish(0)
        log = (self.dock.data_dir / "sidedock.log").read_text(encoding="utf-8")
        self.assertIn("startup version=test", log)
        self.assertIn("type=ValueError", log)
        self.assertIn("event loop interval=", log)
        self.assertIn("shutdown exit_code=0", log)
        self.assertNotIn("PRIVATE_CONTENT", log)


@unittest.skipUnless(sys.platform == "win32", "SideDock uses Windows APIs")
class EdgeGuardTests(unittest.TestCase):
    def setUp(self):
        self.api = self.enterContext(patch.object(windowing, "user32", Mock()))
        self.api.GetCursorPos.return_value = True
        self.api.GetAsyncKeyState.return_value = 0
        self.api.GetForegroundWindow.return_value = 20
        self.api.GetWindowLongW.return_value = 0
        self.api.IsZoomed.return_value = False
        self.api.MonitorFromPoint.return_value = 30
        self.api.GetMonitorInfoW.side_effect = self.monitor_info
        self.api.GetWindowRect.side_effect = self.window_rect
        self.foreground = wintypes.RECT(0, 0, 1920, 1200)

    @staticmethod
    def monitor_info(_monitor, info):
        info._obj.rcMonitor = wintypes.RECT(0, 0, 1920, 1200)
        return True

    def window_rect(self, _hwnd, rect):
        ctypes.memmove(rect, ctypes.byref(self.foreground), ctypes.sizeof(self.foreground))
        return True

    def test_fullscreen_blocks_but_snapped_and_other_monitor_allow(self):
        self.assertFalse(windowing.edge_available(10))
        self.foreground = wintypes.RECT(960, 0, 1920, 1160)
        self.assertTrue(windowing.edge_available(10))
        self.foreground = wintypes.RECT(-1920, 0, 0, 1200)
        self.assertTrue(windowing.edge_available(10))

    def test_captioned_maximized_window_allows_even_with_hidden_taskbar(self):
        self.api.IsZoomed.return_value = True
        self.api.GetWindowLongW.return_value = windowing.WS_CAPTION
        self.assertTrue(windowing.edge_available(10))

    def test_input_desktop_unavailable_and_active_mouse_drag_block_poll(self):
        self.api.GetCursorPos.return_value = False
        self.assertFalse(windowing.edge_available(10, polling=True))
        self.api.GetCursorPos.return_value = True
        self.api.GetAsyncKeyState.return_value = -32768
        self.api.GetForegroundWindow.return_value = None
        self.assertFalse(windowing.edge_available(10, polling=True))
        self.assertTrue(windowing.edge_available(10))

    def test_hit_diagnostics_distinguish_dock_children_from_obstruction(self):
        self.api.WindowFromPoint.return_value = 11
        self.api.GetAncestor.return_value = 10
        self.assertTrue(windowing.pointer_hits_dock(10))
        self.api.GetAncestor.return_value = 20
        self.assertFalse(windowing.pointer_hits_dock(10))
        self.api.WindowFromPoint.return_value = None
        self.assertIsNone(windowing.pointer_hits_dock(10))
