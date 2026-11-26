import tempfile
import unittest
from pathlib import Path

from sidedock.storage import orphaned_managed_copies, cleanup_orphaned_copies


class OrphanCleanupTests(unittest.TestCase):
    def test_cleanup_preserves_references_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            saved = directory / ("a" * 32 + "_keep.pdf")
            orphan = directory / ("b" * 32 + "_old.pdf")
            image = directory / ("img_" + "c" * 32 + ".png")
            unrelated = directory / "important-personal-notes.txt"
            for file in (saved, orphan, image, unrelated):
                file.write_bytes(b"x")
            items = [{"type": "file", "path": str(saved)}]
            self.assertEqual(set(orphaned_managed_copies(directory, items)), {orphan, image})
            self.assertEqual(cleanup_orphaned_copies(directory, items), 2)
            self.assertTrue(saved.exists())
            self.assertTrue(unrelated.exists())
            self.assertFalse(orphan.exists())
            self.assertFalse(image.exists())

if __name__ == "__main__":
    unittest.main()
