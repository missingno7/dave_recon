"""TLINK lays out the whole program exactly as the original.

tools/link_probe.py links C0S + src/DAVE.C, CONFIG.C, HARDWARE.C (compiled)
+ src/asm/lowlevel.asm, tiles.asm (assembled) + stand-in objects for the
data-only module and the far data blobs (tools/omf_writer.py, original
bytes) + CS.LIB with the pinned TLINK 3.0, and compares the result with the
unpacked original: every load-module byte, all relocations and the MZ
header fields TLINK decides (load size, minalloc/maxalloc, SS:SP, CS:IP).
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@unittest.skipUnless((ROOT / "toolchain" / "BIN" / "TCC.EXE").exists()
                     and (ROOT / "toolchain" / "BIN" / "TLINK.EXE").exists(), "toolchain not installed")
class LinkProbeTest(unittest.TestCase):
    def test_load_module_identical(self):
        report = ROOT / "build" / "link_probe_report.json"
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "link_probe.py"), "--json", str(report)],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rep = json.loads(report.read_text())
        self.assertTrue(rep["load_module"]["identical"], rep["load_module"]["diff_runs"][:10])
        self.assertTrue(rep["relocations"]["equal"])
        for field, v in rep["header"].items():
            self.assertEqual(v["linked"], v["original"], field)


if __name__ == "__main__":
    unittest.main()
