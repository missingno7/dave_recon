"""Native subsystems are equivalent to the original over the oracle's boundary
snapshots (tools/native_check.py). Needs an oracle run with boundaries
(python tools/oracle.py tests/oracle/attract_boundaries.txt) and CMake + MinGW."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
RUN = ROOT / "build" / "oracle" / "attract_boundaries" / "run1"


@unittest.skipUnless((RUN / "boundaries.bin").exists(), "no oracle boundary run")
class NativeEquivalenceTest(unittest.TestCase):
    def test_animate_tiles(self):
        import native_check
        r = native_check.check("animate_tiles", RUN)
        self.assertTrue(r["equivalent"], r)
        self.assertGreater(r["ticks_where_original_changed_state"], 0)


if __name__ == "__main__":
    unittest.main()
