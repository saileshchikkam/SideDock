"""Presentation-only labels; clipboard payloads remain unchanged."""
from pathlib import Path
from urllib.parse import urlsplit


def card_kind(item):
    kind = item.get("type")
    if kind == "image":
        return "IMAGE"
    if kind == "file":
        suffix = Path(item.get("name", "")).suffix.lstrip(".").upper()
        return suffix if 0 < len(suffix) <= 8 and suffix.isalnum() else "FILE"
    text = item.get("content", "").strip()
    try:
        url = urlsplit(text)
        if url.scheme in ("http", "https") and url.netloc and not any(c.isspace() for c in text):
            return "LINK"
    except ValueError:
        pass
    return "TEXT"


def preview_text(text, limit=160):
    return text if len(text) <= limit else text[:limit - 1] + "…"
