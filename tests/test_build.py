"""Level D: sources + codecs -> TCC/TASM -> TLINK -> LZEXE reproduce DAVE.EXE exactly."""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@unittest.skipUnless((ROOT / "toolchain" / "LZEXE" / "LZEXE.EXE").exists(), "toolchain not installed")
class HistoricalBuildTest(unittest.TestCase):
    def test_build_reproduces_original_dave_exe(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        report = json.loads((ROOT / "build" / "final" / "report.json").read_text())
        self.assertTrue(report["unpacked_load_module_identical"])
        self.assertTrue(report["header_fields_and_relocations_identical"])
        self.assertTrue(report["packed_identical_to_original_DAVE_EXE"])


if __name__ == "__main__":
    unittest.main()
