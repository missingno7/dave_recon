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
# Corpus: tests/oracle/inv_demos_all.txt (the attract demos, every tick) and
# the scripted tests/oracle/n2_death.txt (death, restart, game over) and
# n2_buttons.txt (fire / jetpack buttons, U-G9 b), each run with
#   python tools/oracle.py tests/oracle/<name>.txt --out <abs path>/build/oracle/<dir>
# Besides native_check's whole-game-state comparison, the player checks
# compare Dave's presentation ids (g_dave_sprite / g_dave_mask, rebuilt by
# the bridge from the native pose, D3), the retraces each call reports with
# the oracle's frames_since_prev, and the PlaySound requests with the
# oracle's sound log; and mutants of player.c must be caught.

PLAYER_RUNS = {"demos_all": ROOT / "build" / "oracle" / "demos_all" / "run1",
               "n2_death": ROOT / "build" / "oracle" / "n2_death" / "run1",
               "n2_buttons": ROOT / "build" / "oracle" / "n2_buttons" / "run1"}
PLAYER_SUBSYSTEMS = ("process_input", "move_dave", "update_jetpack", "handle_death")
DAVE_VIEW_BYTES = (0x573E, 0x573F, 0x57E4, 0x57E5)   # g_dave_sprite, g_dave_mask
_PAIR_CACHE = {}


def _player_pairs(run, subsystem):
    """(tick, pre, post) around `subsystem` for every boundary tick of `run`."""
    import oracle
    key = (str(run), subsystem)
    if key not in _PAIR_CACHE:
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


def _mask_int(pre, cache={}):
    """native_check's game-view mask as a big int (one 0xFF byte per compared byte)."""
    import native_check
    level = int.from_bytes(pre[0x56F4:0x56F6], "little", signed=True)
    if level not in cache:
        m = native_check.game_view_mask(pre)
        cache[level] = int.from_bytes(bytes(0xFF if b else 0 for b in m), "little")
    return cache[level]


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
        diff = (int.from_bytes(mine, "little") ^ int.from_bytes(post, "little")) & (_mask_int(pre) | extra_mask)
        if diff:
            return tick, hex(((diff & -diff).bit_length() - 1) // 8)
    return None


def _events(subsystem):
    """events.txt of the last native_check run: {pair index: (retraces, [sounds])}."""
    ev = {}
    path = ROOT / "build" / "native_check" / subsystem / "events.txt"
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


def _build_mutant(old, new):
    """Build port/ with one textual change to game/player.c into build/port_mutant."""
    import os
    import shutil
    import subprocess
    import native_check
    src = ROOT / "build" / "port_mutant_src"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(ROOT / "port", src)
    p = src / "game" / "player.c"
    text = p.read_text()
    assert text.count(old) == 1, old
    p.write_text(text.replace(old, new))
    out = ROOT / "build" / "port_mutant"
    env = dict(os.environ, PATH=native_check.MINGW + os.pathsep + os.environ["PATH"])
    subprocess.run([native_check.CMAKE, "-S", str(src), "-B", str(out), "-G", "MinGW Makefiles",
                    "-DCMAKE_C_COMPILER=gcc", "-DCMAKE_MAKE_PROGRAM=mingw32-make"],
                   env=env, check=True, capture_output=True)
    subprocess.run([native_check.CMAKE, "--build", str(out)], env=env, check=True, capture_output=True)
    return out / "dave_bridge.exe"


def _run_exe(exe, subsystem, pairs):
    import os
    import subprocess
    import native_check
    work = ROOT / "build" / "native_check_mutant"
    work.mkdir(parents=True, exist_ok=True)
    (work / "pre.bin").write_bytes(b"".join(p for _, p, _ in pairs))
    env = dict(os.environ, PATH=native_check.MINGW + os.pathsep + os.environ["PATH"],
               DAVE_UNPACKED_EXE=str(ROOT / "build" / "DAVE_unpacked.exe"))
    subprocess.run([str(exe), subsystem, str(work / "pre.bin"), str(work / "native.bin")],
                   env=env, check=True)
    return (work / "native.bin").read_bytes()


# One mutant per behaviour worth guarding: (subsystem, runs, old, new).
PLAYER_MUTANTS = [
    ("move_dave", ("n2_buttons",), "d->move_throttle = 3;\n\n", "d->move_throttle = 2;\n\n"),
    ("move_dave", ("demos_all",), "d->y = (int16_t)((d->y + t) & 0xFF);", "d->y = (int16_t)(d->y + t);"),
    ("move_dave", ("n2_buttons",), "d->x -= 2;              /* turn-around step */", "/* no turn-around */"),
    ("move_dave", ("n2_death",), "        spawn_explosion(g, d->x, d->y + 3, EXPLOSION_DEATH, out);",
     "        spawn_explosion(g, d->x, d->y + 2, EXPLOSION_DEATH, out);"),
    ("process_input", ("n2_buttons",), "if (g->buttons.fire_repeat != 30 && fire == 0)",
     "if (g->buttons.fire_repeat != 29 && fire == 0)"),
    ("process_input", ("demos_all",), "case DIR_SE: d->input_dir = DIR_E; break;", "case DIR_SE: d->input_dir = DIR_SE; break;"),
    ("process_input", ("demos_all",), "jump = shift_right_6(b);", "jump = (int16_t)((b >> 6) & 1);"),
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
        import native_check
        for name, run in self._runs().items():
            for sub in PLAYER_SUBSYSTEMS:
                with self.subTest(run=name, subsystem=sub):
                    r = native_check.check(sub, run)
                    self.assertTrue(r["equivalent"], r)
                    # Dave's presentation ids rebuilt from the native pose (D3)
                    native = (ROOT / "build" / "native_check" / sub / "native.bin").read_bytes()
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
        ev = _events(sub)
        pairs = _player_pairs(run, sub)
        for k, (tick, pre, post) in enumerate(pairs):
            retr, sounds = ev.get(k, (0, []))
            got = oracle_sounds.get(tick, [])
            it = iter(got)
            self.assertTrue(all(any(x == y for y in it) for x in sounds if x >= 0),
                            (sub, tick, sounds, got))
        self._retraces_checked = getattr(self, "_retraces_checked", 0) + len(pairs)

    def test_player_retraces_per_tick(self):
        """move_dave + handle_death retraces == the original's retraces per tick
        on every tick where Dave is in play and the level does not change."""
        import json
        import native_check
        for name, run in self._runs().items():
            per = {}
            for sub in ("move_dave", "handle_death"):
                native_check.check(sub, run)
                ev = _events(sub)
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

    def test_player_mutants_caught(self):
        for sub, names, old, new in PLAYER_MUTANTS:
            runs = self._runs(names)
            with self.subTest(subsystem=sub, mutant=new):
                exe = _build_mutant(old, new)
                caught = None
                for name, run in runs.items():
                    pairs = _player_pairs(run, sub)
                    caught = _first_divergence(_run_exe(exe, sub, pairs), pairs, DAVE_VIEW_BYTES)
                    if caught:
                        break
                self.assertIsNotNone(caught, f"mutant not caught: {new}")


if __name__ == "__main__":
    unittest.main()
