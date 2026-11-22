import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sidedock.storage import MAX_ITEMS, atomic_write_json, can_capture, file_digest, managed_bytes


class StorageTests(unittest.TestCase):
    def test_history_limit_without_eviction(self):
        items = [{}] * MAX_ITEMS
        self.assertFalse(can_capture(items))
        self.assertEqual(len(items), MAX_ITEMS)
        self.assertTrue(can_capture(items[:-1]))

    def test_atomic_roundtrip_and_failed_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.json"
            first = [{"content": "  code\n"}]
            atomic_write_json(path, first)
            self.assertEqual(json.loads(path.read_text()), first)
            with patch("sidedock.storage.os.replace", side_effect=OSError("blocked")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, [])
            self.assertEqual(json.loads(path.read_text()), first)
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_file_digest_and_managed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            first, second = directory / "a", directory / "b"
            first.write_bytes(b"abc")
            second.write_bytes(b"abc")
            self.assertEqual(file_digest(first), file_digest(second))
            second.write_bytes(b"abcd")
            self.assertNotEqual(file_digest(first), file_digest(second))
            self.assertEqual(managed_bytes(directory), 7)


if __name__ == "__main__":
    unittest.main()
