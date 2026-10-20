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
    def test_bridge_identity(self):
        import native_check
        r = native_check.check("identity", RUN)
        self.assertTrue(r["equivalent"], r)

    def test_animate_tiles(self):
        import native_check
        r = native_check.check("animate_tiles", RUN)
        self.assertTrue(r["equivalent"], r)
        self.assertGreater(r["ticks_where_original_changed_game_state"], 0)


# ---- world (N3): collisions, pickups, level completion, warps, attract mode.
# Runs: python tools/oracle.py tests/oracle/n3_<name>.txt --out build/oracle/n3_<name>
N3_RUNS = {name: ROOT / "build" / "oracle" / f"n3_{name}" / "run1"
           for name in ("level1_complete", "attract_demos", "out_of_range_demo")}


def _n3(name):
    return unittest.skipUnless((N3_RUNS[name] / "boundaries.bin").exists(),
                               f"no oracle run n3_{name}")


class WorldEquivalenceTest(unittest.TestCase):
    def check(self, subsystem, run, min_changed=1):
        import native_check
        r = native_check.check(subsystem, N3_RUNS[run])
        self.assertTrue(r["equivalent"], r)
        self.assertGreaterEqual(r["ticks_where_original_changed_game_state"], min_changed, r)
        return r

    def mutant(self, subsystem, run, path, old, new):
        import native_check
        r = native_check.check(subsystem, N3_RUNS[run], (path, old, new))
        self.assertFalse(r["equivalent"], f"mutation {old!r} -> {new!r} in {path} not caught")

    @_n3("attract_demos")
    def test_check_collisions(self):
        self.check("check_collisions", "attract_demos")
        # Dave's shot kills score (level + 1) * 100
        self.mutant("check_collisions", "attract_demos", "game/world.c",
                    "(g->level.index + 1) * 100", "(g->level.index + 1) * 101")

    @_n3("attract_demos")
    def test_pick_up_items_demos(self):
        self.check("pick_up_items", "attract_demos")

    @_n3("level1_complete")
    def test_pick_up_items_level1(self):
        self.check("pick_up_items", "level1_complete")
        # the gem value table (100 points for tile 47)
        self.mutant("pick_up_items", "level1_complete", "game/items.c",
                    "{2000, 0, 0, 1000, 100,", "{2000, 0, 0, 1000, 110,")

    @_n3("level1_complete")
    def test_level_complete(self):
        self.check("level_complete", "level1_complete")
        # wait_for_input animates the tiles 20 times per blink
        self.mutant("level_complete", "level1_complete", "game/level.c",
                    "out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);\n"
                    "        for (int i = 0; i < 10; i++)",
                    "out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);\n"
                    "        for (int i = 0; i < 9; i++)")

    @_n3("level1_complete")
    def test_check_warp_transition_no_warp(self):
        # no warp in the corpus: the call must leave everything unchanged
        self.check("check_warp_transition", "level1_complete", min_changed=0)

    @_n3("level1_complete")
    def test_attract_mode_game_start(self):
        self.check("attract_mode", "level1_complete")

    @_n3("attract_demos")
    def test_attract_mode_demo_choice(self):
        self.check("attract_mode", "attract_demos")
        # load_level's srand(100)
        self.mutant("attract_mode", "attract_demos", "game/level.c",
                    "#define LEVEL_SEED 100", "#define LEVEL_SEED 101")

    @_n3("out_of_range_demo")
    def test_attract_mode_out_of_range_demo(self):
        # U-M1 item 4: rand() == 32767 picks offsets[5]; level byte from the CGA tileset
        self.check("attract_mode", "out_of_range_demo")
        self.mutant("attract_mode", "out_of_range_demo", "game/attract.c",
                    "#define DEMO_GARBAGE_START_LEVEL 2", "#define DEMO_GARBAGE_START_LEVEL 3")


if __name__ == "__main__":
    unittest.main()
