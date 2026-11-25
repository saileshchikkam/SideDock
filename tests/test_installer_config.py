"""Release packaging contract tests, safe to run on non-Windows machines."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallerContractTests(unittest.TestCase):
    def test_per_user_installer_preserves_data(self):
        script = (ROOT / "installer" / "SideDock.iss").read_text(encoding="utf-8")
        self.assertIn("PrivilegesRequired=lowest", script)
        self.assertIn(r"DefaultDirName={localappdata}\Programs\SideDock", script)
        self.assertIn(r"LicenseFile=..\LICENSE", script)
        self.assertIn(r"RunKey := 'Software\Microsoft\Windows\CurrentVersion\Run'", script)
        self.assertIn("CompareText(Trim(Value)", script)
        self.assertNotIn("[UninstallDelete]", script)
        self.assertIn("Never delete SideDockData", script)

    def test_build_checks_exact_binary_and_uninstall(self):
        source = (ROOT / "scripts" / "build_installer.py").read_text(encoding="utf-8")
        self.assertIn("hashlib.sha256", source)
        self.assertIn('unins000.exe', source)
        self.assertIn('checksum_line(installer)', source)
        self.assertIn('verify_installer(installer, portable)', source)


if __name__ == "__main__":
    unittest.main()
