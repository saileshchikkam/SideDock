"""Opt-in, local screenshot text recognition using an installed Tesseract CLI.

Tesseract is not bundled. No screenshots are sent over the network.
"""
import ctypes
import os
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path


def find_tesseract():
    # In packaged builds, prefer the runtime shipped with SideDock over
    # machine-wide installations. It is extracted by PyInstaller on launch.
    bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "ocr" / "tesseract.exe"
    if bundle.is_file():
        return str(bundle)
    binary = shutil.which("tesseract")
    if binary:
        return binary
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            candidate = Path(base) / "Tesseract-OCR" / "tesseract.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def extract_text_from_png(png_bytes, executable=None, timeout=20):
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Screenshot is not a PNG image")
    if len(png_bytes) > 50 * 1024 * 1024:
        raise ValueError("Screenshot is too large for OCR")
    binary = executable or find_tesseract()
    if not binary:
        raise FileNotFoundError("Tesseract OCR is not installed")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as stream:
            stream.write(png_bytes)
            temporary = Path(stream.name)
        # A bundled tessdata directory keeps OCR fully offline and independent
        # of any machine-wide language model or registry configuration.
        environment = os.environ.copy()
        tessdata = Path(binary).parent / "tessdata"
        if tessdata.is_dir():
            environment["TESSDATA_PREFIX"] = str(tessdata)
        # PyInstaller sets the Windows DLL search path to its extraction root.
        # The bundled Tesseract DLLs reside beside tesseract.exe in /ocr, not
        # that root. Reset it while launching the helper to avoid DLL conflicts.
        args = [binary, str(temporary), "stdout", "-l", "eng", "--psm", "6"]
        if tessdata.is_dir():
            args.extend(["--tessdata-dir", str(tessdata)])
        environment["PATH"] = str(Path(binary).parent) + os.pathsep + environment.get("PATH", "")
        options = dict(
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=environment,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        frozen = bool(getattr(sys, "frozen", False))
        if frozen and sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.SetDllDirectoryW(None)
            try:
                result = subprocess.run(args, **options)
            finally:
                kernel32.SetDllDirectoryW(str(sys._MEIPASS))
        else:
            result = subprocess.run(args, **options)
        return result.stdout.strip()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
