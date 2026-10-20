"""Opt-in (slow): every scenario of the oracle corpus is reproducible under the
FIDELITY.md contract (`oracle.py --repeat 2`). Enable with DAVE_ORACLE_TESTS=1;
the 413 s all-demos scenario (~20 min) additionally needs DAVE_ORACLE_LONG=1."""
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = sorted((ROOT / "tests" / "oracle").glob("*.txt"))
LONG = {"attract_all_demos"}


@unittest.skipUnless(os.environ.get("DAVE_ORACLE_TESTS") == "1", "set DAVE_ORACLE_TESTS=1")
class OracleDeterminismTest(unittest.TestCase):
    def test_corpus_is_reproducible(self):
        for scenario in CORPUS:
            if scenario.stem in LONG and os.environ.get("DAVE_ORACLE_LONG") != "1":
                continue
            with self.subTest(scenario=scenario.stem):
                r = subprocess.run([sys.executable, str(ROOT / "tools" / "oracle.py"),
                                    str(scenario), "--repeat", "2"],
                                   cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("EQUIVALENT", r.stdout)


if __name__ == "__main__":
    unittest.main()
