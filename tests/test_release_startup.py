"""Distribution constraints: one user-facing EXE and opt-out Windows autostart."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SingleInstallerTests(unittest.TestCase):
    def test_only_one_executable_in_artifact(self):
        workflow = (ROOT / ".github/workflows/windows-build.yml").read_text(encoding="utf-8")
        self.assertIn("name: SideDock-Windows-Installer", workflow)
        self.assertIn("path: dist/SideDock-Setup-*.exe", workflow)
        self.assertNotIn("            dist/SideDock.exe\n", workflow)
        self.assertNotIn("            dist/SHA256SUMS.txt\n", workflow)

    def test_startup_on_by_default_and_disable_available(self):
        installer = (ROOT / "installer/SideDock.iss").read_text(encoding="utf-8")
        self.assertIn('Name: "autostart"', installer)
        self.assertIn('Tasks: autostart', installer)
        self.assertIn('Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"', installer)
        task_line = next(line for line in installer.splitlines() if 'Name: "autostart"' in line)
        self.assertNotIn("Flags: unchecked", task_line)
        self.assertIn('RegDeleteValue(HKCU, RunKey,', installer)
        self.assertIn('CompareText(Trim(Value)', installer)

    def test_installer_checks_startup_and_uninstall(self):
        source = (ROOT / "scripts/build_installer.py").read_text(encoding="utf-8")
        self.assertIn('"/TASKS=autostart"', source)
        self.assertIn('winreg.QueryValueEx(key, "SideDock")', source)
        self.assertIn("uninstaller left an obsolete startup entry", source)
        self.assertIn('runtime / "ocr" / "tesseract.exe"', source)

    def test_fast_start_runtime_is_installed_not_extracted_on_every_login(self):
        builder = (ROOT / "scripts/build_windows.py").read_text(encoding="utf-8")
        installer = (ROOT / "installer/SideDock.iss").read_text(encoding="utf-8")
        self.assertIn('"--onedir"', builder)
        self.assertIn('"--contents-directory", "_internal"', builder)
        self.assertNotIn('"--onefile"', builder)
        self.assertIn(r'Source: "..\dist\SideDock\*"', installer)
        self.assertIn("recursesubdirs createallsubdirs", installer)


if __name__ == "__main__":
    unittest.main()
