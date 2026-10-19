"""Every recovered game source compiles to EXACTLY the original bytes.

Runs tools/verify_sources.py (batch compile of the src/*.C units, strict link with
every fixup resolved) and then tools/reconstruct.py, which takes MATCHING_C
regions from that compiler output rather than raw extracts.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@unittest.skipUnless((ROOT / "toolchain" / "BIN" / "TCC.EXE").exists(), "toolchain not installed")
class MatchingSourcesTest(unittest.TestCase):
    def test_all_sources_exact_and_image_rebuilds(self):
        report = ROOT / "build" / "verify.json"
        v = subprocess.run([sys.executable, str(ROOT / "tools" / "verify_sources.py"),
                            "--json", str(report)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        results = json.loads(report.read_text())
        manifest = json.loads((ROOT / "layout" / "manifest.json").read_text())
        claimed = {r["id"]: r for r in manifest["regions"] if r["kind"] == "MATCHING_C"}
        verified = {pathlib.Path(r["source"]).stem: r for r in results if r["verdict"] == "EXACT"}
        self.assertEqual(set(claimed), set(verified), "manifest MATCHING_C set != EXACT sources")
        for rid, region in claimed.items():
            self.assertEqual((region["start"], region["end"]),
                             (verified[rid]["file_start"], verified[rid]["file_end"]), rid)
        subprocess.run([sys.executable, str(ROOT / "tools" / "extract_raw.py")], cwd=ROOT,
                       capture_output=True, check=True)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "reconstruct.py")], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
