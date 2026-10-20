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


# ---- player (N2): process_input, move_dave, update_jetpack, handle_death ----
#
# Corpus: tests/oracle/inv_demos_all.txt and n2_demos.txt (the attract demos,
# every tick) and the scripted tests/oracle/n2_death.txt (death, restart, game over) and
# n2_buttons.txt (fire / jetpack buttons, U-G9 b), each run with
#   python tools/oracle.py tests/oracle/<name>.txt --out <abs path>/build/oracle/<dir>
# Besides native_check's whole-game-state comparison, the player checks
# compare Dave's presentation ids (g_dave_sprite / g_dave_mask, rebuilt by
# the bridge from the native pose, D3), the retraces each call reports with
# the oracle's frames_since_prev, and the PlaySound requests with the
# oracle's sound log; and mutants of player.c must be caught.

PLAYER_RUNS = {"demos_all": ROOT / "build" / "oracle" / "demos_all" / "run1",
               "n2_demos": ROOT / "build" / "oracle" / "n2_demos" / "run1",
               "n2_death": ROOT / "build" / "oracle" / "n2_death" / "run1",
               "n2_buttons": ROOT / "build" / "oracle" / "n2_buttons" / "run1",
               # the world lane's runs (live level 1, the out-of-range demo's garbage stream)
               "n3_level1_complete": ROOT / "build" / "oracle" / "n3_level1_complete" / "run1",
               "n3_out_of_range_demo": ROOT / "build" / "oracle" / "n3_out_of_range_demo" / "run1"}
PLAYER_SUBSYSTEMS = ("process_input", "move_dave", "update_jetpack", "handle_death")
DAVE_VIEW_BYTES = (0x573E, 0x573F, 0x57E4, 0x57E5)   # g_dave_sprite, g_dave_mask
_PAIR_CACHE = {}


def _player_pairs(run, subsystem):
    """(tick, pre, post) around `subsystem` for every boundary tick of `run`."""
    import oracle
    key = (str(run), subsystem)
    if key not in _PAIR_CACHE:
        _PAIR_CACHE.clear()      # keep one run's pairs only (a run can be ~1 GB)
        sites = [n for _, n in oracle.PIPELINE]
        after = sites[sites.index(subsystem) + 1]
        pairs, cur = [], None
        for tick, site, snap in oracle.iter_boundaries(run / "boundaries.bin"):
            if site == subsystem:
                cur = (tick, snap)
            elif site == after and cur and cur[0] == tick:
                pairs.append((tick, cur[1], snap))
        _PAIR_CACHE[key] = pairs
    return _PAIR_CACHE[key]


def _mask_int(pre, post):
    """native_check's game-view mask as a big int (one 0xFF byte per compared byte)."""
    import native_check
    return native_check._mask_int(native_check.game_view_mask(pre, post))


def _first_divergence(native, pairs, extra=()):
    """First tick whose native snapshot differs from the original's after-state
    on the game view (plus the `extra` DS offsets), or None."""
    import oracle
    L = oracle.DGROUP_LIVE_LEN
    extra_mask = 0
    for a in extra:
        extra_mask |= 0xFF << (8 * a)
    for k, (tick, pre, post) in enumerate(pairs):
        mine = native[k * L:(k + 1) * L]
        diff = (int.from_bytes(mine, "little") ^ int.from_bytes(post, "little")) & (_mask_int(pre, post) | extra_mask)
        if diff:
            return tick, hex(((diff & -diff).bit_length() - 1) // 8)
    return None


_CHECKED = {}


def _checked(run, subsystem):
    """native_check.check(subsystem, run), once per test session, with the
    native snapshots and the parsed events of that run."""
    import native_check
    key = (str(run), subsystem)
    if key not in _CHECKED:
        r = native_check.check(subsystem, run)
        work = ROOT / "build" / "native_check" / subsystem
        _CHECKED[key] = (r, (work / "native.bin").read_bytes(), _parse_events(work / "events.txt"))
    return _CHECKED[key]


def _parse_events(path):
    """events.txt: {pair index: (retraces, [sounds])}."""
    ev = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        k = int(parts[0])
        r, s = ev.get(k, (0, []))
        if parts[1] == "retraces":
            r = int(parts[2])
        elif parts[1] == "sound":
            s = s + [int(parts[2])]
        ev[k] = (r, s)
    return ev




# One mutant per behaviour worth guarding: (subsystem, runs, old, new).
PLAYER_MUTANTS = [
    ("move_dave", ("n2_buttons",), "d->move_throttle = 3;\n\n", "d->move_throttle = 2;\n\n"),
    ("move_dave", ("demos_all",), "d->y = (int16_t)((d->y + t) & 0xFF);", "d->y = (int16_t)(d->y + t);"),
    ("move_dave", ("n2_buttons",), "d->x -= 2;              /* turn-around step */", "/* no turn-around */"),
    ("move_dave", ("n2_death",), "spawn_explosion(g, d->x, (int16_t)(d->y + 3), EXPLOSION_DAVE, out);",
     "spawn_explosion(g, d->x, (int16_t)(d->y + 2), EXPLOSION_DAVE, out);"),
    ("process_input", ("n2_buttons",), "        g->buttons.fire_repeat = 30;\n        if (g->inv.has_gun",
     "        g->buttons.fire_repeat = 31;\n        if (g->inv.has_gun"),
    ("process_input", ("n2_buttons",), "if (g->buttons.jetpack_repeat != 30 && jump == 0)",
     "if (g->buttons.jetpack_repeat != 30 && jump == 0 && 0)"),
    ("process_input", ("demos_all",), "case DIR_SE: d->input_dir = DIR_E; break;", "case DIR_SE: d->input_dir = DIR_SE; break;"),
    # (the signed `byte >> 6` jump quirk is unobservable in the shipped demos:
    # every fire byte meets a jetpack counter at 30, see the ledger)
    ("move_dave", ("n2_demos", "demos_all"), "        g->dave.anim_delay = 2;\n        g->dave.anim_frame = (int16_t)((g->dave.anim_frame + 1) & 3);\n        dave_set_pose(g, POSE_CLIMB",
     "        g->dave.anim_delay = 3;\n        g->dave.anim_frame = (int16_t)((g->dave.anim_frame + 1) & 3);\n        dave_set_pose(g, POSE_CLIMB"),
    ("move_dave", ("n2_demos", "demos_all"), "        d->anim_delay = 4;", "        d->anim_delay = 3;"),
    ("update_jetpack", ("n2_demos", "demos_all"), "g->inv.fuel_tick = 15;", "g->inv.fuel_tick = 14;"),
    ("handle_death", ("n2_death",), "d->death_timer = (int16_t)(d->death_timer - 1);",
     "d->death_timer = (int16_t)(d->death_timer - 2);"),
    ("handle_death", ("n2_death",), "d->facing = DIR_RIGHT;\n    if (g->level.in_warp_zone",
     "d->facing = DIR_LEFT;\n    if (g->level.in_warp_zone"),
]


class NativePlayerTest(unittest.TestCase):
    def _runs(self, names=None):
        runs = {k: v for k, v in PLAYER_RUNS.items()
                if (v / "boundaries.bin").exists() and (names is None or k in names)}
        if not runs:
            self.skipTest("no player oracle run (tests/oracle/inv_demos_all.txt, n2_*.txt)")
        return runs

    def test_player_subsystems_equivalent(self):
        for name, run in self._runs().items():
            for sub in PLAYER_SUBSYSTEMS:
                with self.subTest(run=name, subsystem=sub):
                    r, native, _ = _checked(run, sub)
                    self.assertTrue(r["equivalent"], r)
                    # Dave's presentation ids rebuilt from the native pose (D3)
                    self.assertIsNone(_first_divergence(native, _player_pairs(run, sub), DAVE_VIEW_BYTES))
                    if sub in ("move_dave", "handle_death"):
                        self._check_retraces_and_sounds(run, sub)

    def _check_retraces_and_sounds(self, run, sub):
        """Retraces: during play/demo ticks, the waits of move_dave plus
        handle_death are the whole tick's retraces unless another
        subsystem waited (level_complete / warp / menus: checked via the
        tick's state). Sounds: the native PlaySound requests are a
        subsequence of the tick's PlaySound calls in the original."""
        import json
        ticks = {json.loads(l)["tick"]: json.loads(l) for l in (run / "ticks.jsonl").read_text().splitlines()}
        oracle_sounds = {}
        for l in (run / "sounds.jsonl").read_text().splitlines():
            s = json.loads(l)
            oracle_sounds.setdefault(s["tick"], []).append(s["sound"])
        ev = _checked(run, sub)[2]
        pairs = _player_pairs(run, sub)
        for k, (tick, pre, post) in enumerate(pairs):
            retr, sounds = ev.get(k, (0, []))
            got = oracle_sounds.get(tick, [])
            it = iter(got)
            self.assertTrue(all(any(x == y for y in it) for x in sounds if x >= 0),
                            (sub, tick, sounds, got))

    def test_player_retraces_per_tick(self):
        """move_dave + handle_death retraces == the original's retraces per tick
        on every tick where Dave is in play and the level does not change."""
        import json
        for name, run in self._runs().items():
            per = {}
            for sub in ("move_dave", "handle_death"):
                ev = _checked(run, sub)[2]
                for k, (tick, _, _) in enumerate(_player_pairs(run, sub)):
                    per[tick] = per.get(tick, 0) + ev.get(k, (0, []))[0]
            rows = {json.loads(l)["tick"]: json.loads(l) for l in (run / "ticks.jsonl").read_text().splitlines()}
            checked = bad = 0
            for tick, r in per.items():
                a, b = rows.get(tick), rows.get(tick + 1)
                if not a or not b or a["game_state"] not in (0, 1) or b["game_state"] != a["game_state"] \
                        or a["level"] != b["level"]:
                    continue
                checked += 1
                if r != b["frames_since_prev"]:
                    bad += 1
            with self.subTest(run=name):
                self.assertGreater(checked, 0)
                self.assertEqual(bad, 0, f"{bad} of {checked} ticks")

    def test_player_bridge_mutants_caught(self):
        """The `<name>/mutant` bridge entries (bridge.c) must diverge."""
        import native_check
        where = {"process_input": "n2_buttons", "move_dave": "n2_buttons",
                 "update_jetpack": "n2_demos", "handle_death": "n2_death"}
        for sub, name in where.items():
            run = self._runs((name,))[name]
            with self.subTest(subsystem=sub):
                r = native_check.check(sub, run, variant=sub + "/mutant")
                self.assertFalse(r["equivalent"], r)

    def test_player_mutants_caught(self):
        """Source mutants of game/player.c (native_check's `mutation`)."""
        import native_check
        for sub, names, old, new in PLAYER_MUTANTS:
            runs = self._runs(names)
            with self.subTest(subsystem=sub, mutant=new):
                caught = None
                for name, run in runs.items():
                    r = native_check.check(sub, run, mutation=("game/player.c", old, new))
                    if not r["equivalent"]:
                        caught = r["first_divergence"]
                        break
                self.assertIsNotNone(caught, f"mutant not caught: {new}")


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
        # (the level byte now comes from resources.demo_overrun: read one byte further)
        self.mutant("attract_mode", "out_of_range_demo", "game/attract.c",
                    "return (int8_t)r->demo_overrun[pos - DEMO_BANK_BYTES];",
                    "return (int8_t)r->demo_overrun[pos - DEMO_BANK_BYTES + 1];")


if __name__ == "__main__":
    unittest.main()
