"""Free-running native replay against the original (PORT_ROADMAP M3.3).

Imports the original's state ONCE, at the head of a start tick of an oracle
run, then runs the native game_tick() (port/game/game.c) for every following
tick with nothing from the original but the INPUTS (port/tests/replay/
replay.c): the scenario's key events (one evolving key table and BIOS key
slot), the emulated time of each tick head (when the frame is delivered) and
time(NULL) (from seeds.jsonl, state-model D7). After every tick the native
state, exported into a copy of the start snapshot, must equal the original's
next tick head on native_check's game view (the same mask); the PlaySound
requests of the tick must equal sounds.jsonl, and the retraces the tick
waited must equal the next tick's frames_since_prev (FIDELITY.md section 3
timing exemptions; plus ticks with WaitSound, whose length is the
asynchronous sound driver's).

    python tools/native_replay.py --run build/oracle/n3_level1_complete/run1
    python tools/native_replay.py --run ... --start 2 --ticks 500
    python tools/native_replay.py --run ... --mutate game/items.c "60;" "59;"   (must diverge)

The run ends where the original leaves the pipeline: a pass that sets
game_over (main() then runs check_high_score before the next observed tick
head) or a menu request the port does not run (game.h). The last compared
tick is the one before.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import native_check  # noqa: E402
import oracle  # noqa: E402

L = oracle.DGROUP_LIVE_LEN
SOUND_WAIT = -4                     # output.h enum sound_control
STATUS = {0: "continue", 1: "game_over", 2: "menu"}

# readable names of the compared bytes (docs/semantic-inventory.json ids;
# record layouts as in port/tests/bridge/dgroup_map.c)
_STRUCTS = {
    "g_monsters": (8, ["active", "x", "y", "path_pos", "reload", "sprite", "anim_count",
                       "anim_frame", "fire_count", "move_count"], 2, "soa"),
    "g_shots": (14, ["active", "x", "y", "dir", "frame", "kind", "owner"], 2, "aos"),
    "g_actors": (0x13A, ["active", "x", "y", "frame", "life", "anim", "type"], 2, "aos"),
    "g_anim_tiles": (12, ["active", "first", "cur", "col", "row", "count"], 2, "aos"),
    "g_hiscores": (7, ["level", "level", "score16", "score16", "init0", "init1", "init2"], 1, "aos"),
}


def _inventory():
    inv = json.loads((ROOT / "docs" / "semantic-inventory.json").read_text())
    entries = inv["entries"] if isinstance(inv["entries"], list) else list(inv["entries"].values())
    out = []
    for e in entries:
        if isinstance(e, dict) and e.get("role") == "game_state":
            out.append((int(e["identity"]["ds"], 16), e["identity"]["size"], e["id"].split(":")[1]))
    return sorted(out)


_INV = None


def field_name(ds: int) -> str:
    global _INV
    if _INV is None:
        _INV = _inventory()
    for lv in range(-1, 10):
        m = (0x173A + 0x500 * lv + 0x100) & 0xFFFF
        if m <= ds < m + 1000:
            row, col = divmod(ds - m, 100)
            return f"g_levels[{lv}].map[row {row}][col {col}]"
    for a, size, name in _INV:
        if a <= ds < a + size:
            off = ds - a
            if name in _STRUCTS:
                stride, fields, width, kind = _STRUCTS[name]
                if kind == "soa":       # g_monsters: field k = int[4] at 8 * k
                    k, i = divmod(off, stride)
                    if k < len(fields):
                        return f"{name}.{fields[k]}[{i // 2}]"
                else:
                    i, f = divmod(off, stride)
                    idx = f // width
                    if idx < len(fields):
                        return f"{name}[{i}].{fields[idx]}"
                    return f"{name}[{i}]+{f:#x} (tail)"
            return name + (f"+{off:#x}" if off else "")
    return "?"


def named_diff(mine: bytes, orig: bytes, diff: list) -> dict:
    """{field: {native, original}} for the first differing DS offsets
    (16-bit fields as words, map bytes as bytes)."""
    out = {}
    for i in diff[:24]:
        name = field_name(i)
        if name in out:
            continue
        if name.startswith("g_levels") or name.startswith("g_tiles") or "repeat" in name:
            out[name] = {"native": mine[i], "original": orig[i]}
        else:
            a = i & ~1
            out[name] = {"native": int.from_bytes(mine[a:a + 2], "little", signed=True),
                         "original": int.from_bytes(orig[a:a + 2], "little", signed=True)}
    return out


def load_ticks(run: pathlib.Path) -> list:
    return [json.loads(l) for l in (run / "ticks.jsonl").read_text().splitlines()]


def tick_snapshot(run: pathlib.Path, tick: int) -> bytes:
    with open(run / "ticks.bin", "rb") as f:
        f.seek((tick - 1) * L)
        return f.read(L)


def iter_tick_snapshots(run: pathlib.Path, first: int):
    with open(run / "ticks.bin", "rb") as f:
        f.seek((first - 1) * L)
        while True:
            b = f.read(L)
            if len(b) < L:
                return
            yield b


def _keys(snapshot: bytes) -> list:
    """g_keydown (DS 0x8A32, int[128]): the scan codes held."""
    k = oracle.KEYDOWN
    return [i for i in range(128) if snapshot[k + 2 * i] | snapshot[k + 2 * i + 1]]


def first_poll_keys(run: pathlib.Path, rows: list) -> dict:
    """tick -> the key table process_input read, for the ticks whose first
    poll IS process_input's (play and demo heads: attract_mode returns at
    once), where the run has boundary snapshots: g_keydown at the move_dave
    boundary, i.e. right after process_input. process_input never writes
    g_keydown (only the INT 9 handler does), so that table is what its
    get_player_input read unless a key arrived in the few instructions after
    the read. The tick head is earlier: a key delivery in flight can land
    between the head capture and the read (n3_level1_complete tick 210 of
    the 2026-10-20 worktree run: the PageUp release scripted at 15052 ms is
    not in the table at the 15052.60 ms head nor at the process_input
    boundary, but process_input read it: input_dir became 2, not 1). The
    input sample is the table at the read; without boundaries the head's
    table is the best observation the oracle offers."""
    out = {}
    if not (run / "boundaries.bin").exists():
        return out
    states = {r["tick"]: r["game_state"] for r in rows}
    for tick, site, snap in oracle.iter_boundaries(run / "boundaries.bin"):
        if site == "move_dave" and states.get(tick) in (0, 1):
            out[tick] = _keys(snap)
    return out


def write_inputs(run: pathlib.Path, rows: list, first: int, last: int, work: pathlib.Path) -> dict:
    """The replay's inputs (replay.c): video retrace period, key events,
    per tick the head time, time(NULL) and the key table at its first poll."""
    env = native_check.write_world_inputs(run, [], work)    # demo bank, pristine levels
    video = json.loads((run / "summary.json").read_text()).get("video", "vga")
    seeds = native_check.time_seeds(run)
    lines = [f"vbl {oracle.VIDEO[video]['vbl_ms']!r}"]
    lines += [f"event {ms} {kind} {scan}" for ms, kind, scan in native_check.key_events(run)]
    at_read = first_poll_keys(run, rows)
    late = 0
    for r in rows[first - 1:last]:
        t = native_check.time_from_seed(seeds[r["tick"]]) if r["tick"] in seeds else native_check.DOS_EPOCH_1991
        held = at_read.get(r["tick"], r["keys_down"])            # g_keydown at the first poll
        late += held != r["keys_down"]
        keys = ",".join(str(k) for k in held) or "-"
        lines.append(f"tick {r['tick']} start {r['emulated_ms']} time {t} keys {keys}")
    (work / "replay_inputs.txt").write_text("\n".join(lines) + "\n")
    del env["DAVE_BRIDGE_INPUTS"]                            # the bridge's per-call model: not used
    env["_late_key_deliveries"] = str(late)
    env["_key_source"] = "boundaries (after process_input)" if at_read else "tick heads"
    return env


def waitvbl_exits(run: pathlib.Path) -> dict:
    """tick -> WaitVBL calls of that pass, from a per-retrace capture
    (`retraces <n>`: one record per WaitVBL exit, with the pass it belongs
    to). Exact where frames_since_prev (elapsed retrace periods) is not: a
    wait that starts after its retrace has begun waits for the next one
    (WaitVBL is edge-triggered), e.g. CGA scroll steps whose redraw takes
    longer than a frame on the emulated 386. Only passes the capture covers
    entirely (before the pass of the last captured record)."""
    path = run / "retraces.jsonl"
    if not path.exists():
        return {}
    count = {}
    for line in path.read_text().splitlines():
        t = json.loads(line)["tick"]
        count[t] = count.get(t, 0) + 1
    if not count:
        return {}
    last = max(count)
    return {t: n for t, n in count.items() if t < last}


def parse_events(path: pathlib.Path) -> dict:
    ev = {}
    if not path.exists():
        return ev
    for line in path.read_text().splitlines():
        p = line.split()
        if len(p) < 10 or p[0] != "tick":
            continue
        sounds = [] if p[9] == "-" else p[9].split(",")
        ev[int(p[1])] = {"status": int(p[3]), "menu": int(p[5]), "retraces": int(p[7]),
                         "sounds": [int(s) for s in sounds if s != "overflow"],
                         "sound_overflow": "overflow" in sounds}
    return ev


def replay(run: pathlib.Path, start: int | None = None, ticks: int | None = None,
           mutation: tuple | None = None, name: str | None = None) -> dict:
    """Free-run the native game from `start` (default: tick 1, the first
    pipeline pass) for `ticks` ticks (default: to the end of the run)."""
    rows = load_ticks(run)
    first = start or 1
    last = len(rows) - 1 if ticks is None else min(len(rows) - 1, first + ticks - 1)
    name = name or run.parent.name
    work = ROOT / "build" / "native_replay" / (name + ("_mutant" if mutation else ""))
    work.mkdir(parents=True, exist_ok=True)
    (work / "start.bin").write_bytes(tick_snapshot(run, first))
    bridge = native_check.build_mutant(mutation) if mutation else native_check.build_port()
    exe = bridge.with_name("dave_replay.exe")
    env = dict(os.environ, PATH=native_check.MINGW + os.pathsep + os.environ["PATH"])
    inputs = write_inputs(run, rows, first, last, work)
    late, key_source = inputs.pop("_late_key_deliveries"), inputs.pop("_key_source")
    env.update(inputs)
    events_path = work / "events.txt"
    proc = subprocess.Popen([str(exe), str(work / "start.bin"), str(work / "replay_inputs.txt"),
                             str(events_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    # 1. state: native after tick t vs the original's head of tick t + 1
    state_div, compared = None, 0
    originals = iter_tick_snapshots(run, first)
    pre = next(originals)
    tick = first
    try:
        for post in originals:
            if tick > last:
                break
            mine = proc.stdout.read(L)
            if len(mine) < L:
                break                       # the replay stopped: game over / menu / poll limit
            diff = native_check._masked_diff(mine, post, native_check.game_view_mask(pre, post))
            if diff:
                state_div = {"tick": tick, "kind": "state", "ds_offsets": [hex(i) for i in diff[:24]],
                             "fields": named_diff(mine, post, diff)}
                break
            compared += 1
            pre, tick = post, tick + 1
    finally:
        if state_div:
            proc.kill()
        _, err = proc.communicate()
    ev = parse_events(events_path)

    # 2. per pass: the PlaySound requests (sounds.jsonl: the tick a PlaySound
    # ran in) and the retraces waited (the next head's frames_since_prev),
    # for every pass whose pre-state matched
    sounds = {}
    for line in (run / "sounds.jsonl").read_text().splitlines():
        x = json.loads(line)
        sounds.setdefault(x["tick"], []).append(x["sound"])
    by_tick = {r["tick"]: r for r in rows}
    sound_div, retrace_divs, waitvbl_divs, exempt_timing = None, [], [], []
    waits = waitvbl_exits(run)
    passes = 0
    for t in range(first, first + compared + (1 if state_div else 0)):
        e, nxt = ev.get(t), by_tick.get(t + 1)
        if e is None or nxt is None:
            break
        passes += 1
        nat = [x for x in e["sounds"] if x >= 0]
        if (nat != sounds.get(t, []) or e["sound_overflow"]) and sound_div is None:
            sound_div = {"tick": t, "kind": "sound", "native": nat, "original": sounds.get(t, [])}
        if t in waits and e["retraces"] != waits[t]:
            waitvbl_divs.append((t, e["retraces"], waits[t]))
        if e["retraces"] != nxt["frames_since_prev"]:
            row = (t, e["retraces"], nxt["frames_since_prev"])
            if SOUND_WAIT in e["sounds"] and e["retraces"] < nxt["frames_since_prev"]:
                # WaitSound blocks on the PIT-driven driver: it can only ADD time
                exempt_timing.append(row + ("WaitSound: the asynchronous sound driver",))
            elif by_tick[t]["game_state"] in oracle.TIMING_EXEMPT_STATES or nxt["game_state"] == 3:
                exempt_timing.append(row + ("title / high-score prompt (FIDELITY.md 3)",))
            else:
                retrace_divs.append(row)
    retrace_div = None
    if retrace_divs:
        t, n, o = retrace_divs[0]
        retrace_div = {"tick": t, "kind": "retraces", "native": n, "original": o}
    waitvbl_div = None
    if waitvbl_divs:
        t, n, o = waitvbl_divs[0]
        waitvbl_div = {"tick": t, "kind": "waitvbl_calls", "native": n, "original": o}
    divs = [d for d in (state_div, sound_div, retrace_div, waitvbl_div) if d]
    stop = ev.get(first + compared) if state_div is None else None
    return {
        "run": str(run), "start": first,
        "equivalent": not divs,
        "state_equivalent": state_div is None, "sounds_equivalent": sound_div is None,
        "retraces_equivalent": retrace_div is None,
        "waitvbl_calls_equivalent": waitvbl_div is None,
        "waitvbl_ticks_compared": sum(1 for t in waits if first <= t < first + passes),
        "compared": compared, "last_compared_tick": first + compared - 1, "run_ticks": len(rows),
        "first_divergence": min(divs, key=lambda d: d["tick"]) if divs else None,
        "state_divergence": state_div, "sound_divergence": sound_div,
        "retrace_divergences": retrace_divs[:24], "retrace_divergence_count": len(retrace_divs),
        "waitvbl_divergences": waitvbl_divs[:24],
        # why the state comparison ended without a divergence
        "stopped": (None if state_div else
                    STATUS.get(stop["status"]) if stop and stop["status"] else
                    "end of run" if first + compared > last else "replay ended"),
        "sound_requests_compared": sum(len(sounds.get(t, [])) for t in range(first, first + passes)),
        "timing_exempt_count": len(exempt_timing), "timing_exempt": exempt_timing[:12],
        "key_table_source": key_source,
        "key_deliveries_between_head_and_read": int(late),
        "stderr": err.decode(errors="replace").strip()[-2000:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=pathlib.Path, required=True)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--ticks", type=int, default=None)
    ap.add_argument("--mutate", nargs=3, metavar=("FILE", "OLD", "NEW"))
    args = ap.parse_args()
    r = replay(args.run, args.start, args.ticks, tuple(args.mutate) if args.mutate else None)
    print(json.dumps(r, indent=1))
    ok = r["equivalent"] != bool(args.mutate)   # a mutant must diverge
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
