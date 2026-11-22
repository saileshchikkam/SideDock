"""Bounded, local clipboard persistence helpers (no Qt dependency)."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

MAX_ITEMS = 500
MAX_TEXT_BYTES = 256 * 1024
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_MANAGED_BYTES = 500 * 1024 * 1024


def can_capture(items):
    """Never evict existing history automatically."""
    return len(items) < MAX_ITEMS


def managed_bytes(directory):
    return sum(p.stat().st_size for p in Path(directory).iterdir() if p.is_file())


def file_digest(path):
    digest = hashlib.md5()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path, data):
    """Replace only after a complete temporary write; preserve the prior index on failure."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
