"""Windows CI regression: in-place SideDock v1.0.1 to v1.0.2 upgrade.

Uses disposable installer and user data. Refuses to touch an existing SideDockData.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import winreg

OLD_URL = (
    "https://github.com/saileshchikkam/SideDock/releases/download/"
    "v1.0.1/SideDock-Setup-1.0.1.exe"
)
OLD_SHA256 = "cb74c9113f3e4c42d96d915ecda59ccf6005b301f3fe6cce259eef8dfe483767"
ROOT = Path(__file__).resolve().parents[1]
NEW_INSTALLER = ROOT / "dist" / "SideDock-Setup-1.0.2.exe"
NEW_APP = ROOT / "dist" / "SideDock" / "SideDock.exe"
AUTORUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install(installer, folder):
    subprocess.run(
        [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
         "/NOICONS", "/TASKS=autostart", f"/DIR={folder}"],
        check=True, timeout=240,
    )
    exe = folder / "SideDock.exe"
    if not exe.is_file():
        raise AssertionError(f"Installed executable missing: {exe}")
    subprocess.run([str(exe), "--smoke-test"], check=True, timeout=60)
    return exe


def assert_autorun(exe):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_KEY) as key:
        command, _ = winreg.QueryValueEx(key, "SideDock")
    if Path(command.strip('"')).resolve() != exe.resolve():
        raise AssertionError("HKCU autorun must match the installed executable")


def main():
    if sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("This destructive fixture test is restricted to GitHub Windows CI")
    if not NEW_INSTALLER.is_file() or not NEW_APP.is_file():
        raise FileNotFoundError("Build the candidate installer before the upgrade test")
    data_dir = Path.home() / "SideDockData"
    if data_dir.exists():
        raise RuntimeError("Refusing upgrade test: SideDockData already exists")
    with tempfile.TemporaryDirectory(prefix="sidedock-upgrade-") as temporary:
        temporary = Path(temporary)
        old_installer = temporary / "SideDock-Setup-1.0.1.exe"
        installation = temporary / "SideDock"
        urllib.request.urlretrieve(OLD_URL, old_installer)
        if sha256(old_installer) != OLD_SHA256:
            raise RuntimeError("Official v1.0.1 installer hash mismatch")
        expected = {}
        try:
            old_app = install(old_installer, installation)
            assert_autorun(old_app)
            data_dir.mkdir()
            (data_dir / "files").mkdir()
            fixtures = {
                "items.json": [
                    {"type": "text", "content": "upgrade clipboard fixture", "pinned": True},
                    {"type": "note", "content": "upgrade notes fixture", "pinned": False},
                ],
                "settings.json": {
                    "mode": "deep_dark", "side": "right", "y": None,
                    "capture_paused": True, "shortcuts_enabled": False,
                },
            }
            for filename, payload in fixtures.items():
                path = data_dir / filename
                path.write_text(json.dumps(payload), encoding="utf-8")
                expected[filename] = sha256(path)
            attachment = data_dir / "files" / "upgrade-test-file.txt"
            attachment.write_text("SideDock fixture", encoding="utf-8")
            expected[str(attachment.relative_to(data_dir))] = sha256(attachment)

            updated_app = install(NEW_INSTALLER, installation)
            assert_autorun(updated_app)
            if sha256(updated_app) != sha256(NEW_APP):
                raise AssertionError("Upgraded binary differs from the v1.0.2 build")
            for relative, before in expected.items():
                path = data_dir / relative
                if not path.is_file() or sha256(path) != before:
                    raise AssertionError(f"Upgrade modified or lost {relative}")
            for filename, payload in fixtures.items():
                if json.loads((data_dir / filename).read_text(encoding="utf-8")) != payload:
                    raise AssertionError(f"Upgrade corrupted {filename}")

            uninstaller = installation / "unins000.exe"
            if not uninstaller.is_file():
                raise AssertionError("Upgraded installation has no uninstaller")
            subprocess.run(
                [str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                check=True, timeout=240,
            )
            if updated_app.exists():
                raise AssertionError("Uninstall left the executable")
            for relative, before in expected.items():
                path = data_dir / relative
                if not path.is_file() or sha256(path) != before:
                    raise AssertionError(f"Uninstall modified or lost {relative}")
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_KEY) as key:
                    winreg.QueryValueEx(key, "SideDock")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("Uninstall left the autorun entry")
            print("PASS: verified 1.0.1 -> 1.0.2 in-place upgrade, "
                  "history/notes/settings/data persistence, startup registry and uninstall")
        finally:
            if data_dir.exists():
                shutil.rmtree(data_dir)


if __name__ == "__main__":
    main()
