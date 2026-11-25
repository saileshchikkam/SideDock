"""Build and smoke-test the portable SideDock Windows executable."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sidedock.distribution import checksum_line, ico_bytes
from sidedock.version import __version__


def version_resource():
    version = tuple(int(part) for part in __version__.split("."))
    if len(version) != 3 or any(not 0 <= part <= 65535 for part in version):
        raise ValueError("Expected a three-part Windows-compatible version")
    numeric = version + (0,)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric}, prodvers={numeric},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'SideDock'),
    StringStruct('FileDescription', 'SideDock Windows productivity dock'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('InternalName', 'SideDock'),
    StringStruct('OriginalFilename', 'SideDock.exe'),
    StringStruct('ProductName', 'SideDock'),
    StringStruct('ProductVersion', '{__version__}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"""


def main():
    if sys.platform != "win32":
        raise SystemExit("Build SideDock.exe on Windows.")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray, QBuffer, QIODevice
    from PySide6.QtWidgets import QApplication
    from sidedock.branding import app_icon
    app = QApplication([])
    icon = app_icon()
    output = ROOT / "build" / "release"
    output.mkdir(parents=True, exist_ok=True)
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.WriteOnly)
        if not icon.pixmap(size, size).save(buffer, "PNG"):
            raise RuntimeError("Could not render application icon")
        images.append((size, bytes(array)))
        buffer.close()
    icon_path = output / "SideDock.ico"
    icon_path.write_bytes(ico_bytes(images))
    version_path = output / "version.txt"
    version_path.write_text(version_resource(), encoding="utf-8")
    ocr_root = Path(os.environ.get("SIDEDOCK_OCR_DIR", ""))
    if not os.environ.get("SIDEDOCK_OCR_DIR") or not (ocr_root / "tesseract.exe").is_file():
        raise RuntimeError("SIDEDOCK_OCR_DIR must point to a Tesseract OCR installation for this release")
    if not (ocr_root / "tessdata" / "eng.traineddata").is_file():
        raise RuntimeError("English OCR language model is missing")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--noconsole", "--name", "SideDock",
        "--icon", str(icon_path), "--version-file", str(version_path),
        "--add-data", f"{ocr_root};ocr",
        "--paths", str(ROOT), "--specpath", str(output),
        "--workpath", str(output / "work"), "--distpath", str(ROOT / "dist"),
        str(ROOT / "sidedock" / "__main__.py"),
    ], cwd=ROOT, check=True)
    exe = ROOT / "dist" / "SideDock.exe"
    subprocess.run([str(exe), "--smoke-test"], cwd=ROOT, check=True, timeout=120)
    diagnostic = ROOT / "build" / "ocr-smoke-diagnostic.txt"
    diagnostic.unlink(missing_ok=True)
    try:
        subprocess.run([str(exe), "--smoke-test-ocr"], cwd=ROOT, check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        details = diagnostic.read_text(encoding="utf-8") if diagnostic.is_file() else "No packaged OCR diagnostic produced."
        raise RuntimeError("Packaged OCR smoke test failed:\\n" + details) from exc
    (exe.parent / "SHA256SUMS.txt").write_text(checksum_line(exe), encoding="ascii")
    print(f"Verified build: {exe}")


if __name__ == "__main__":
    main()
