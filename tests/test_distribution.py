import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from sidedock.autostart import startup_command
from sidedock.distribution import checksum_line, ico_bytes
from sidedock.version import __version__


class DistributionTests(unittest.TestCase):
    def test_startup_commands(self):
        self.assertEqual(startup_command("C:/Program Files/SideDock/SideDock.exe", True), '"' + str(Path('C:/Program Files/SideDock/SideDock.exe')) + '"')
        self.assertTrue(startup_command("C:/Python/python.exe", False, True).endswith("pythonw.exe -m sidedock"))
        self.assertTrue(startup_command("C:/Python/python.exe").endswith("python.exe -m sidedock"))

    def test_icon_container(self):
        png = b"\x89PNG\r\n\x1a\n" + b"payload"
        ico = ico_bytes([(16, png), (256, png)])
        self.assertEqual(struct.unpack_from("<HHH", ico), (0, 1, 2))
        self.assertEqual(ico[6], 16)
        self.assertEqual(ico[22], 0)
        self.assertEqual(struct.unpack_from("<I", ico, 18)[0], 38)
        self.assertEqual(ico[38:], png + png)
        with self.assertRaises(ValueError):
            ico_bytes([(512, png)])

    def test_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "SideDock.exe"
            exe.write_bytes(b"example")
            self.assertEqual(checksum_line(exe), hashlib.sha256(b"example").hexdigest() + "  SideDock.exe\n")

    def test_version(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
