"""The packing layer: LZEXE 0.91 on the unpacked image == the original DAVE.EXE."""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@unittest.skipUnless((ROOT / "toolchain" / "LZEXE" / "LZEXE.EXE").exists(), "LZEXE not installed")
class RepackTest(unittest.TestCase):
    def test_repacking_unpacked_image_reproduces_original(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "repack.py"), "--oracle"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
