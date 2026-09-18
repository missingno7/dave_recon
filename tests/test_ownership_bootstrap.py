import hashlib
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reconstruct  # noqa: E402


class OwnershipBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.manifest = reconstruct.load_manifest()

    def test_manifest_covers_full_image_with_no_gaps_or_overlaps(self):
        regions = reconstruct.validate_ownership(self.manifest)
        self.assertEqual(regions[0]["start"], 0)
        self.assertEqual(regions[-1]["end"], self.manifest["unpacked_original"]["size"])

    def test_rejects_invalid_kind(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["regions"][0]["kind"] = "NOT_A_REAL_KIND"
        with self.assertRaises(SystemExit):
            reconstruct.validate_ownership(manifest)

    def test_rejects_gap(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["regions"][1]["start"] += 1
        with self.assertRaises(SystemExit):
            reconstruct.validate_ownership(manifest)

    def test_rejects_overlap(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["regions"][1]["start"] -= 1
        with self.assertRaises(SystemExit):
            reconstruct.validate_ownership(manifest)

    def test_reconstruction_matches_unpacked_image_exactly(self):
        raw_dir = ROOT / "raw"
        if not any(raw_dir.glob("*.bin")):
            subprocess.run([sys.executable, str(ROOT / "tools" / "extract_raw.py")],
                            check=True, cwd=ROOT)
        image, _ = reconstruct.reconstruct(self.manifest)
        self.assertEqual(len(image), self.manifest["unpacked_original"]["size"])
        self.assertEqual(hashlib.md5(image).hexdigest(), self.manifest["unpacked_original"]["md5"])


if __name__ == "__main__":
    unittest.main()
