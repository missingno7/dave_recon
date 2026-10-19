"""The _BSS storage names in src/DAVE.H reproduce the game BSS map.

tools/bss_names.py --check: the hash order (tools/codegen_lab/bss_order.py)
of every unit's storage names puts each variable at its DS offset in
layout/bss-map.json, the units' variables fill their _BSS extents, the
#define lines in DAVE.H are exactly the map's renames, and DAVE.H declares
each unit's variables in address order (ties keep first-appearance order).
The compiler-level proof is tests/test_matching_sources.py.
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bss_names  # noqa: E402


class BssNamesTest(unittest.TestCase):
    def test_check_passes(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "bss_names.py"), "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_map_tiles_game_bss(self):
        doc = json.loads((ROOT / "layout" / "bss-map.json").read_text())
        pos = doc["range"][0]
        for unit in doc["units"]:
            self.assertEqual(unit["bss"][0], pos, unit["unit"])
            for e in unit["entries"]:
                self.assertEqual(e["ds"], pos, (unit["unit"], e))
                pos += e["size"]
            self.assertEqual(pos, unit["bss"][1], unit["unit"])
        self.assertEqual(pos, doc["range"][1])

    def test_solver_is_stable(self):
        """Re-solving gives the committed storage names."""
        doc = json.loads((ROOT / "layout" / "bss-map.json").read_text())
        for unit in doc["units"]:
            vs = bss_names.unit_vars(unit)
            self.assertEqual(bss_names.solve_unit(vs), [v["storage"] for v in vs], unit["unit"])


if __name__ == "__main__":
    unittest.main()
