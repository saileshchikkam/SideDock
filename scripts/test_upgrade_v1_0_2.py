"""Windows CI regression: v1.0.1 and original v1.0.2 to revised v1.0.2.

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
RELEASE_102_API = "https://api.github.com/repos/saileshchikkam/SideDock/releases/tags/v1.0.2"
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


def fetch_official_v102(destination):
    """Verify the public v1.0.2 binary against its current GitHub asset digest.

    It may be the initial public build or a revised v1.0.2 build; avoid
    hard-coding the old digest after the public asset has been refreshed.
    """
    request = urllib.request.Request(
        RELEASE_102_API, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SideDock-Windows-CI",
        }
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        metadata = json.load(response)
    if metadata.get("tag_name") != "v1.0.2" or metadata.get("draft"):
        raise RuntimeError("Public v1.0.2 release missing or not published")
    asset = next(
        (item for item in metadata.get("assets", [])
         if item.get("name") == "SideDock-Setup-1.0.2.exe"), None
    )
    if not asset or not asset.get("digest", "").startswith("sha256:"):
        raise RuntimeError("Official v1.0.2 asset or digest missing")
    urllib.request.urlretrieve(asset["browser_download_url"], destination)
    if sha256(destination) != asset["digest"].removeprefix("sha256:"):
        raise RuntimeError("Official v1.0.2 release digest mismatch")


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
        public_v102 = temporary / "public-v1.0.2-installer.exe"
        installation = temporary / "SideDock"
        urllib.request.urlretrieve(OLD_URL, old_installer)
        if sha256(old_installer) != OLD_SHA256:
            raise RuntimeError("Official v1.0.1 installer hash mismatch")
        fetch_official_v102(public_v102)
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

            # A public post-launch v1.0.2 user must also be able to install
            # the revised *same-version* setup over their existing program.
            prior_v102_app = install(public_v102, installation)
            assert_autorun(prior_v102_app)
            for relative, before in expected.items():
                path = data_dir / relative
                if not path.is_file() or sha256(path) != before:
                    raise AssertionError(f"Public v1.0.2 upgrade changed {relative}")

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
            print("PASS: verified 1.0.1 -> public v1.0.2 -> revised v1.0.2 "
                  "in-place upgrades, history/notes/settings/data persistence, "
                  "startup registry and uninstall")
        finally:
            if data_dir.exists():
                shutil.rmtree(data_dir)


if __name__ == "__main__":
    main()
