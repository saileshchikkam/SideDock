"""Platform-independent helpers for Windows release artifacts."""
import hashlib
import struct
from pathlib import Path


def ico_bytes(images):
    """Build a Windows ICO container from (square size, PNG bytes) pairs."""
    if not images or any(not 1 <= size <= 256 or not png.startswith(b"\x89PNG\r\n\x1a\n") for size, png in images):
        raise ValueError("ICO requires PNG images sized 1–256 px")
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = []
    payload = []
    for size, png in images:
        dimension = size % 256
        entries.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(png), offset))
        payload.append(png)
        offset += len(png)
    return header + b"".join(entries) + b"".join(payload)


def checksum_line(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"{digest.hexdigest()}  {path.name}\n"
