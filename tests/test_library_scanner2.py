import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import library_scanner2 as ls2  # noqa: E402


class LibraryScanner2Test(unittest.TestCase):
    """The whole library area [0x9613,0xb50b) tiles with 59 CS.LIB modules, every
    non-fixup byte matches, and every fixup re-derives from the layout."""

    @classmethod
    def setUpClass(cls):
        needed = [ROOT / "toolchain" / "LIB" / "CS.LIB", ROOT / "toolchain" / "LIB" / "C0S.OBJ",
                  ROOT / "build" / "DAVE_unpacked.exe"]
        if not all(p.exists() for p in needed):
            raise unittest.SkipTest("toolchain / unpacked image not installed locally")
        cls.A = ls2.run_all()
        cls.R = ls2.build_report(cls.A)

    def test_library_text_tiles_completely(self):
        A = self.A
        self.assertEqual(A.tile_problems, [])
        self.assertEqual(A.text_place[0]["start"], 0x9613)
        self.assertEqual(A.text_place[-1]["end"], 0xB50B)
        self.assertEqual(len(A.text_place), 59)
        pos = A.text_place[0]["start"]
        for p in A.text_place:
            self.assertEqual(p["start"] - p["pad_before"], pos)
            pos = p["end"]
        self.assertTrue(all(pad["all_zero"] for pad in A.pads))

    def test_link_order_is_library_order(self):
        idx = [self.A.index[p["module"]] for p in self.A.text_place]
        self.assertEqual(idx, sorted(idx))

    def test_every_module_identified_with_zero_unexplained_bytes(self):
        for m in self.R["modules"] + self.R["data_only_modules"]:
            self.assertTrue(m["identified"], m["module"])

    def test_fixups_have_no_mismatch(self):
        t = self.A.fixup_totals
        self.assertEqual(t["mismatch"], 0)
        self.assertEqual(t["unverified"], 0)
        self.assertGreater(t["verified"], 300)

    def test_every_root_is_called_by_game_or_c0s(self):
        self.assertEqual(self.A.roots_unexplained, [])
        self.assertEqual(self.A.unresolved_externs, ["_main"])

    def test_call_sites_reproduce_the_call_graph_census(self):
        self.assertEqual(self.A.census_edges_found, self.A.census_edges_total)
        self.assertEqual(self.A.call_unnamed, [])


if __name__ == "__main__":
    unittest.main()
