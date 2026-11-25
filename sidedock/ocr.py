"""Opt-in, local screenshot text recognition using an installed Tesseract CLI.

Tesseract is not bundled. No screenshots are sent over the network.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def find_tesseract():
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
        result = subprocess.run(
            [binary, str(temporary), "stdout", "-l", "eng"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.stdout.strip()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
