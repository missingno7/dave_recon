"""Opt-in (slow, ~2 min): the original's behaviour is reproducible under the
FIDELITY.md contract. Enable with DAVE_ORACLE_TESTS=1."""
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@unittest.skipUnless(os.environ.get("DAVE_ORACLE_TESTS") == "1", "set DAVE_ORACLE_TESTS=1")
class OracleDeterminismTest(unittest.TestCase):
    def test_attract_with_boundaries_is_reproducible(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "oracle.py"),
                            str(ROOT / "tests" / "oracle" / "attract_boundaries.txt"), "--repeat", "2"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("EQUIVALENT", r.stdout)


if __name__ == "__main__":
    unittest.main()
