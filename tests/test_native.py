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


# --- N1: monsters, shots, explosions over the five built-in demos ----------
# Oracle run: python tools/oracle.py tests/oracle/inv_demos_all.txt
#             --out <absolute path>/build/oracle/demos_all
DEMOS = ROOT / "build" / "oracle" / "demos_all" / "run1"
MONSTER_SPRITE_DS = 0x576A   # g_monsters.sprite[4]


def _c_array(path, name):
    import re
    text = (ROOT / path).read_text()
    body = re.search(name + r"\[\d*\] = \{(.*?)\};", text, re.S).group(1)
    return [int(v) for v in re.findall(r"-?\d+", re.sub(r"/\*.*?\*/", "", body, flags=re.S))]


def _sprite_ids_checked(test, run):
    """Compare g_monsters.sprite after the native move_monsters (the last
    native_check of it, on `run`) with the original's; returns ticks compared."""
    import oracle
    native = (ROOT / "build" / "native_check" / "move_monsters" / "native.bin").read_bytes()
    L, k, cur = oracle.DGROUP_LIVE_LEN, 0, None
    for tick, site, snap in oracle.iter_boundaries(run / "boundaries.bin"):
        if site == "move_monsters":
            cur = tick
        elif site == "move_bullets" and cur == tick:
            mine = native[k * L:(k + 1) * L]
            test.assertEqual(mine[MONSTER_SPRITE_DS:MONSTER_SPRITE_DS + 8],
                             snap[MONSTER_SPRITE_DS:MONSTER_SPRITE_DS + 8], "tick %d" % tick)
            k += 1
    return k


class NativeConstantsTest(unittest.TestCase):
    """The constant windows the native code keeps for out-of-range reads equal
    the original's initialised data (docs/semantic-inventory.json file offsets)."""

    def _words(self, ident, count):
        import json
        import struct
        inv = json.loads((ROOT / "docs" / "semantic-inventory.json").read_text())
        entries = inv["entries"] if isinstance(inv["entries"], list) else list(inv["entries"].values())
        e = next(e for e in entries if isinstance(e, dict) and e["id"] == ident)
        exe = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
        at = int(e["identity"]["file"], 16)
        return list(struct.unpack_from("<%dh" % count, exe, at))

    @unittest.skipUnless((ROOT / "build" / "DAVE_unpacked.exe").exists(), "run tools/bootstrap.py")
    def test_tile_attr_window(self):
        window = _c_array("port/game/level_probe.c", "tile_attr_window")
        self.assertEqual(len(window), 256)
        # index t + 128 for t = -128..127: starts 128 words before g_tile_attr
        self.assertEqual(window, self._words("data:g_spr_shot_b0", 256))
        self.assertEqual(window[128:128 + 53], self._words("data:g_tile_attr", 53))

    @unittest.skipUnless((ROOT / "build" / "DAVE_unpacked.exe").exists(), "run tools/bootstrap.py")
    def test_monster_size_window(self):
        window = _c_array("port/game/monsters.c", "monster_size_window")
        self.assertEqual(window, self._words("data:g_level_start_y", 26))
        self.assertEqual(window[10:18], self._words("data:g_monster_width", 8))
        self.assertEqual(window[18:26], self._words("data:g_monster_height", 8))


@unittest.skipUnless((DEMOS / "boundaries.bin").exists(), "no demos_all oracle run")
class NativeMonstersShotsExplosionsTest(unittest.TestCase):
    results = {}     # one check per subsystem (each pass over the corpus takes minutes)

    def _equivalent(self, name):
        import native_check
        if name not in self.results:
            self.results[name] = native_check.check(name, DEMOS)
        r = self.results[name]
        self.assertTrue(r["equivalent"], r)
        self.assertGreater(r["ticks_where_original_changed_game_state"], 0, r)
        return r

    def _mutant_caught(self, name):
        import native_check
        r = native_check.check(name, DEMOS, variant=name + "/mutant")
        self.assertFalse(r["equivalent"], r)

    def test_update_explosions(self):
        self._equivalent("update_explosions")
        self._mutant_caught("update_explosions")

    def test_move_monsters(self):
        self._equivalent("move_monsters")
        self._mutant_caught("move_monsters")

    def test_move_monsters_sprite_ids(self):
        """Beyond the game view: the per-mode sprite ids the bridge rebuilds
        from shown_frame (D3) equal the original's after every tick (VGA)."""
        self._equivalent("move_monsters")
        self.assertGreater(_sprite_ids_checked(self, DEMOS), 0)

    def test_move_bullets(self):
        self._equivalent("move_bullets")
        self._mutant_caught("move_bullets")


# EGA / CGA runs of demo 2 (level 4): python tools/oracle.py
# tests/oracle/n1_ega_demo2.txt (n1_cga_demo2.txt) --out <abs>/build/oracle/n1_ega_demo2
N1_MODE_RUNS = {"ega": ROOT / "build" / "oracle" / "n1_ega_demo2" / "run1",
                "cga": ROOT / "build" / "oracle" / "n1_cga_demo2" / "run1"}


class NativeMonstersOtherModesTest(unittest.TestCase):
    """Same subsystems in EGA (mode 0Dh) and CGA (mode 4): the game state
    must not depend on the mode, and the bridge's per-mode monster sprite
    ids must match the original's."""

    def _run(self, mode):
        import native_check
        run = N1_MODE_RUNS[mode]
        if not (run / "boundaries.bin").exists():
            self.skipTest("no %s oracle run" % mode)
        for name in ("update_explosions", "move_bullets", "move_monsters"):
            r = native_check.check(name, run)
            self.assertTrue(r["equivalent"], r)
        self.assertGreater(_sprite_ids_checked(self, run), 0)

    def test_ega(self):
        self._run("ega")

    def test_cga(self):
        self._run("cga")

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
