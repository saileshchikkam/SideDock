"""Build and verify SideDock's fast-start per-user Windows installer.

Run after scripts/build_windows.py on Windows with Inno Setup 6.
"""
import hashlib
import os
import winreg
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sidedock.distribution import checksum_line
from sidedock.version import __version__


def find_iscc():
    found = shutil.which("ISCC.exe") or shutil.which("iscc")
    if found:
        return found
    for environment in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(environment)
        if base:
            path = Path(base) / "Inno Setup 6" / "ISCC.exe"
            if path.is_file():
                return str(path)
    raise FileNotFoundError("Inno Setup 6 ISCC.exe was not found")


def installer_path():
    return ROOT / "dist" / f"SideDock-Setup-{__version__}.exe"


def verify_installer(installer, portable_exe):
    """Install to a disposable folder; verify installed binary; uninstall."""
    with tempfile.TemporaryDirectory(prefix="sidedock-install-test-") as directory:
        destination = Path(directory) / "SideDock"
        subprocess.run(
            [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
             "/NOICONS", "/TASKS=autostart", f"/DIR={destination}"],
            check=True, timeout=180,
        )
        installed = destination / "SideDock.exe"
        runtime = destination / "_internal"
        if not (runtime / "ocr" / "tesseract.exe").is_file():
            raise RuntimeError("Installer smoke test: bundled OCR executable missing")
        if not (runtime / "ocr" / "tessdata" / "eng.traineddata").is_file():
            raise RuntimeError("Installer smoke test: English OCR data missing")
        if not installed.is_file():
            raise RuntimeError("Installer smoke test: missing installed executable")
        if hashlib.sha256(installed.read_bytes()).digest() != hashlib.sha256(portable_exe.read_bytes()).digest():
            raise RuntimeError("Installer smoke test: executable differs from portable build")
        # Launch the actual installed folder without onefile unpacking.
        import time
        started = time.perf_counter()
        subprocess.run([str(installed), "--smoke-test"], check=True, timeout=30)
        print(f"Installed SideDock startup smoke: {time.perf_counter() - started:.2f}s")
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            command, _ = winreg.QueryValueEx(key, "SideDock")
        if command.strip('"') != str(installed):
            raise RuntimeError("Installer smoke test: startup entry does not target installed SideDock.exe")
        uninstaller = destination / "unins000.exe"
        if not uninstaller.is_file():
            raise RuntimeError("Installer smoke test: missing uninstaller")
        subprocess.run(
            [str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            check=True, timeout=180,
        )
        if installed.exists():
            raise RuntimeError("Installer smoke test: uninstaller left executable behind")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.QueryValueEx(key, "SideDock")
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError("Installer smoke test: uninstaller left an obsolete startup entry")
    print("Installer installation/uninstallation smoke test passed.")


def main():
    if sys.platform != "win32":
        raise SystemExit("Build the installer on Windows.")
    portable = ROOT / "dist" / "SideDock" / "SideDock.exe"
    resources = (
        portable,
        portable.parent / "_internal" / "ocr" / "tesseract.exe",
        ROOT / "build" / "release" / "SideDock.ico",
        ROOT / "installer" / "SideDock.iss",
        ROOT / "LICENSE",
    )
    for resource in resources:
        if not resource.is_file():
            raise FileNotFoundError(f"Missing installer resource: {resource}")
    subprocess.run(
        [find_iscc(), f"/DMyAppVersion={__version__}", str(ROOT / "installer" / "SideDock.iss")],
        cwd=ROOT, check=True, timeout=180,
    )
    installer = installer_path()
    if not installer.is_file() or installer.stat().st_size < 1024 * 1024:
        raise RuntimeError("Installer was not created or is unexpectedly small")
    with installer.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise RuntimeError("Installer is not a Windows executable")
    verify_installer(installer, portable)
    (ROOT / "dist" / "SHA256SUMS.txt").write_text(
        checksum_line(portable) + checksum_line(installer), encoding="ascii"
    )
    print(f"Verified installer: {installer}")


if __name__ == "__main__":
    main()
