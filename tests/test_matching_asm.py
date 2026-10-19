"""Every hand-written assembly module assembles to EXACTLY the original bytes.

Runs tools/verify_sources.py, whose src/asm/*.asm path assembles every module
with the pinned assembler (layout/assembler.json) and strictly links it
(tools/match_asm.py). Checks that

* every module is EXACT and its assembler output (build/matched/<stem>.bin,
  what tools/reconstruct.py uses for MATCHING_ASM regions) equals the image;
* the modules tile the assembly range cs [0x6f25, 0x9413) with nothing
  between them but single 00 alignment bytes inserted by TLINK;
* any MATCHING_ASM region in layout/manifest.json is backed by an EXACT
  module with the same extent.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HDR = 0x200
ASM_RANGE_CS = (0x6F25, 0x9413)     # after the last C function, up to CS.LIB


def _assembler_installed() -> bool:
    cfg = json.loads((ROOT / "layout" / "assembler.json").read_text())
    exe = ROOT / "toolchain" / "ASM" / cfg["assembler"] / "TASM.EXE"
    return exe.exists() and (ROOT / "toolchain" / "BIN" / "TCC.EXE").exists()


@unittest.skipUnless(_assembler_installed(), "toolchain/assembler not installed")
class MatchingAsmTest(unittest.TestCase):
    def test_all_modules_exact_and_tile_the_asm_range(self):
        report = ROOT / "build" / "verify.json"
        v = subprocess.run([sys.executable, str(ROOT / "tools" / "verify_sources.py"),
                            "--json", str(report)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        results = json.loads((ROOT / "build" / "verify_asm.json").read_text())
        self.assertTrue(results, "no src/asm modules verified")
        image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
        for r in results:
            self.assertEqual(r["verdict"], "EXACT", r["source"])
            built = ROOT / "build" / "matched" / (pathlib.Path(r["source"]).stem + ".bin")
            self.assertEqual(built.read_bytes(), image[r["file_start"]:r["file_end"]], r["source"])

        cursor = ASM_RANGE_CS[0]
        for r in sorted(results, key=lambda r: r["cs_start"]):
            gap = image[HDR + cursor:HDR + r["cs_start"]]
            self.assertLessEqual(len(gap), 1, f"unowned bytes before {r['source']}")
            self.assertEqual(gap.strip(b"\x00"), b"", f"non-zero padding before {r['source']}")
            cursor = r["cs_end"]
        self.assertEqual(cursor, ASM_RANGE_CS[1])

        manifest = json.loads((ROOT / "layout" / "manifest.json").read_text())
        claimed = {g["id"]: g for g in manifest["regions"] if g["kind"] == "MATCHING_ASM"}
        verified = {pathlib.Path(r["source"]).stem: r for r in results}
        for rid, region in claimed.items():
            self.assertIn(rid, verified)
            self.assertEqual((region["start"], region["end"]),
                             (verified[rid]["file_start"], verified[rid]["file_end"]), rid)


if __name__ == "__main__":
    unittest.main()
