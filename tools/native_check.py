"""Differential check of a native subsystem against the original (oracle).

For every tick in an oracle run's boundary stream (tools/oracle.py,
`boundaries <n>`), takes the original DGROUP snapshot just BEFORE the
subsystem ran and the one just AFTER it, runs the native implementation on
the before-state through the test-only bridge (port/tests/bridge), and
requires the native after-state to equal the original after-state on the
gameplay view (FIDELITY.md contract), byte for byte over the whole DGROUP.
Comparing the whole DGROUP (not just the fields the native code owns) also
proves the original subsystem touched nothing the native one ignores.

    python tools/native_check.py animate_tiles [--run build/oracle/attract_boundaries/run1]
    python tools/native_check.py pick_up_items --mutate game/items.c "60;" "59;"

--mutate builds a copy of port/ with one textual replacement (a deliberate
small change) into build/mutant; the check must then report a divergence.

Inputs the world's waiting loops need (port/tests/bridge/world_io.c) are
reconstructed from the run: the scenario's key events (script.txt), the
emulated time of each verified tick head and time(NULL) (ticks.jsonl), and
the demo bank (far segment 0x0B31 of the unpacked DAVE.EXE).

Builds port/ with CMake (MinGW gcc) into build/port first.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import oracle  # noqa: E402

CMAKE = os.environ.get("DAVE_CMAKE", "C:/Program Files/Microsoft Visual Studio/2022/Community/"
                       "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe")
MINGW = os.environ.get("DAVE_MINGW_BIN", "C:/msys64/mingw64/bin")
SITES = [name for _, name in oracle.PIPELINE]

# Game-layer comparisons cover exactly the objects the semantic inventory
# classifies as game_state (docs/semantic-inventory.json), plus the live
# records of the current level (before and after the call) inside g_levels,
# minus documented deferrals. g_tiles is compared: the bridge rebuilds it
# from the level resources and level.index (dgroup_export_levels).
DEFERRED: dict = {}
DEFERRED_RANGES = [(0x5742 + 5 * 8, 0x5742 + 6 * 8,
                    "g_monsters.sprite[4]: per-mode presentation id (state-model D3)")]

# Borland time(): local time + timezone (TZ unset: EST, 5 h) on the pinned DOS
# date 1991-01-01. time(NULL) is an INPUT (state-model D7): the DOS clock runs
# slow while sounds play (U-S3), so it is not a function of emulated time; the
# oracle records every srand argument (seeds.jsonl), and the srand(time) seed
# is the low word of time() = (DOS_EPOCH_1991 + seconds) & 0xFFFF.
DOS_EPOCH_1991 = 662688000 + 5 * 3600
LEVEL_SEED = 100      # load_level's srand(100)

# DOSBox-X mapper names used in scenarios -> PC scan codes (set 1)
SCANCODES = {"esc": 0x01, "enter": 0x1C, "lctrl": 0x1D, "lshift": 0x2A, "lalt": 0x38,
             "space": 0x39, "up": 0x48, "left": 0x4B, "right": 0x4D, "down": 0x50,
             "home": 0x47, "pageup": 0x49, "end": 0x4F, "pagedown": 0x51,
             "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f9": 0x43, "f10": 0x44}
for _row, _first in (("qwertyuiop", 0x10), ("asdfghjkl", 0x1E), ("zxcvbnm", 0x2C)):
    for _k, _c in enumerate(_row):
        SCANCODES[_c] = _first + _k
for _k, _c in enumerate("1234567890"):
    SCANCODES[_c] = 0x02 + _k

_BASE_MASK = None
_FULL_BYTE = bytes([0] + [0xFF] * 255)     # bytes.translate table: nonzero mask byte -> 0xFF


def _base_mask() -> bytearray:
    global _BASE_MASK
    if _BASE_MASK is None:
        inv = json.loads((ROOT / "docs" / "semantic-inventory.json").read_text())
        entries = inv["entries"] if isinstance(inv["entries"], list) else list(inv["entries"].values())
        mask = bytearray(oracle.DGROUP_LIVE_LEN)
        for e in entries:
            if isinstance(e, dict) and e.get("role") == "game_state" and e["id"] not in DEFERRED:
                a = int(e["identity"]["ds"], 16)
                for i in range(a, min(a + e["identity"]["size"], len(mask))):
                    mask[i] = 1
        for a, b, _ in DEFERRED_RANGES:
            mask[a:b] = bytes(b - a)
        _BASE_MASK = mask
    return _BASE_MASK


def game_view_mask(snapshot: bytes, post: bytes | None = None) -> bytearray:
    mask = bytearray(_base_mask())
    for snap in (snapshot, post) if post is not None else (snapshot,):
        level = int.from_bytes(snap[0x56F4:0x56F6], "little", signed=True)
        m = (0x173A + 0x500 * level + 0x100) & 0xFFFF
        mask[m:min(m + 1000, len(mask))] = b"\x01" * (min(m + 1000, len(mask)) - m)
    for lo, hi in oracle.ASYNC_RANGES:
        mask[lo:hi] = bytes(hi - lo)
    return mask


def build_port(src: pathlib.Path = ROOT / "port", out: pathlib.Path = ROOT / "build" / "port") -> pathlib.Path:
    env = dict(os.environ, PATH=MINGW + os.pathsep + os.environ["PATH"])
    subprocess.run([CMAKE, "-S", str(src), "-B", str(out), "-G", "MinGW Makefiles",
                    "-DCMAKE_C_COMPILER=gcc", "-DCMAKE_MAKE_PROGRAM=mingw32-make"],
                   env=env, check=True, capture_output=True)
    r = subprocess.run([CMAKE, "--build", str(out)], env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"build of {src} failed:\n{r.stdout[-4000:]}{r.stderr[-4000:]}")
    return out / "dave_bridge.exe"


def build_mutant(mutation: tuple) -> pathlib.Path:
    """port/ with one textual replacement (path relative to port/, old, new)."""
    rel, old, new = mutation
    src = ROOT / "build" / "mutant" / "port"
    if src.parent.exists():       # clean build: copytree keeps mtimes, make would reuse objects
        shutil.rmtree(src.parent)
    shutil.copytree(ROOT / "port", src)
    f = src / rel
    text = f.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"mutation: {old!r} occurs {text.count(old)} times in {rel}")
    f.write_text(text.replace(old, new))
    return build_port(src, ROOT / "build" / "mutant" / "build")


def time_from_seed(seed: int) -> int:
    """The time(NULL) value whose low word srand received (D7)."""
    return DOS_EPOCH_1991 + ((seed - DOS_EPOCH_1991) & 0xFFFF)


def time_seeds(run: pathlib.Path) -> dict:
    """tick -> the first srand argument of that tick that is not load_level's
    srand(100): attract_mode's srand(time(NULL))."""
    out = {}
    if (run / "seeds.jsonl").exists():
        for line in (run / "seeds.jsonl").read_text().splitlines():
            s = json.loads(line)
            if s["seed"] != LEVEL_SEED and s["tick"] not in out:
                out[s["tick"]] = s["seed"]
    return out


def key_events(run: pathlib.Path) -> list:
    """(ms, 'down'|'up', scan) from the run's acceptance script (key = 50 ms tap)."""
    events = []
    script = run / "script.txt"
    if not script.exists():
        return events
    for line in script.read_text().splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[1] not in ("key", "keydown", "keyup"):
            continue
        ms, cmd, name = int(parts[0]), parts[1], parts[2]
        name = name[4:] if name.startswith("key_") else name
        if name.lower() not in SCANCODES:
            continue
        scan = SCANCODES[name.lower()]
        if cmd == "key":
            events += [(ms, "down", scan), (ms + 50, "up", scan)]
        else:
            events.append((ms, "down" if cmd == "keydown" else "up", scan))
    return sorted(events)


def write_world_inputs(run: pathlib.Path, ticks: list, work: pathlib.Path) -> dict:
    """The bridge's world input file and demo bank (port/tests/bridge/world_io.c)."""
    head = {}
    if (run / "ticks.jsonl").exists():
        for line in (run / "ticks.jsonl").read_text().splitlines():
            r = json.loads(line)
            head[r["tick"]] = r["emulated_ms"]
    lines = [f"event {ms} {kind} {scan}" for ms, kind, scan in key_events(run)]
    seeds = time_seeds(run)
    for k, tick in enumerate(ticks):
        if tick in head:
            t = time_from_seed(seeds[tick]) if tick in seeds else DOS_EPOCH_1991
            lines.append(f"pair {k} start {head[tick]} time {t}")
    (work / "inputs.txt").write_text("\n".join(lines) + "\n")
    import far_data
    import levels
    exe = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
    (work / "demos.bin").write_bytes(far_data.segment_bytes(exe, "demos"))
    _, base, _ = levels.find_levels_base(exe)
    (work / "levels.bin").write_bytes(exe[base:base + levels.NUM_LEVELS * levels.RECORD_SIZE])
    return {"DAVE_BRIDGE_INPUTS": str(work / "inputs.txt"), "DAVE_BRIDGE_DEMOS": str(work / "demos.bin"),
            "DAVE_BRIDGE_LEVELS": str(work / "levels.bin")}


def collect_pairs(subsystem: str, run: pathlib.Path) -> list:
    pairs, cur = [], {}
    if subsystem == "identity":
        # bridge self-check: import + export must reproduce every snapshot
        for tick, site, snap in oracle.iter_boundaries(run / "boundaries.bin"):
            pairs.append((tick, snap, snap))
    else:
        after_site = SITES[SITES.index(subsystem) + 1]
        for tick, site, snap in oracle.iter_boundaries(run / "boundaries.bin"):
            if site == subsystem:
                cur = {"tick": tick, "pre": snap}
            elif site == after_site and cur.get("tick") == tick:
                pairs.append((tick, cur["pre"], snap))
    return pairs


def check(subsystem: str, run: pathlib.Path, mutation: tuple | None = None) -> dict:
    pairs = collect_pairs(subsystem, run)
    work = ROOT / "build" / "native_check" / (subsystem + ("_mutant" if mutation else ""))
    work.mkdir(parents=True, exist_ok=True)
    (work / "pre.bin").write_bytes(b"".join(p for _, p, _ in pairs))
    exe = build_mutant(mutation) if mutation else build_port()
    env = dict(os.environ, PATH=MINGW + os.pathsep + os.environ["PATH"])
    env.update(write_world_inputs(run, [t for t, _, _ in pairs], work))
    subprocess.run([str(exe), subsystem, str(work / "pre.bin"), str(work / "native.bin"),
                    str(work / "events.txt")], env=env, check=True)
    native = (work / "native.bin").read_bytes()
    L = oracle.DGROUP_LIVE_LEN
    changed_in_original = presentation_bytes = 0
    full = bytearray([1]) * L
    for k, (tick, pre, post) in enumerate(pairs):
        mine = native[k * L:(k + 1) * L]
        mask = game_view_mask(pre, post) if subsystem != "identity" else full
        m = int.from_bytes(bytes(mask).translate(_FULL_BYTE), "little")   # 1 -> 0xFF per byte
        changes = int.from_bytes(pre, "little") ^ int.from_bytes(post, "little")
        if changes & m:
            changed_in_original += 1
        nonmask = changes & ~m
        presentation_bytes += sum(1 for b in nonmask.to_bytes(L, "little") if b)
        if (int.from_bytes(mine, "little") ^ int.from_bytes(post, "little")) & m:
            diff = [i for i in range(L) if mask[i] and mine[i] != post[i]]
            return {"subsystem": subsystem, "ticks": len(pairs), "equivalent": False,
                    "first_divergence": {"tick": tick, "ds_offsets": [hex(i) for i in diff[:16]]}}
    events = (work / "events.txt").read_text().splitlines()
    return {"subsystem": subsystem, "ticks": len(pairs), "equivalent": True,
            "ticks_where_original_changed_game_state": changed_in_original,
            "non_game_bytes_changed_by_original": presentation_bytes,
            "events": len(events),
            "retraces": retrace_report(run, [t for t, _, _ in pairs], events)}


def retrace_report(run: pathlib.Path, ticks: list, events: list) -> list:
    """(tick, retraces the native call reported, retraces between this tick head
    and the next one in the oracle): informational, since the rest of the tick
    adds its own waits (usually move_dave's one WaitVBL)."""
    interval = {}
    if (run / "ticks.jsonl").exists():
        for line in (run / "ticks.jsonl").read_text().splitlines():
            r = json.loads(line)
            interval[r["tick"] - 1] = r["frames_since_prev"]
    out = []
    for e in events:
        k, kind, *rest = e.split()
        if kind == "retraces" and len(out) < 20:
            tick = ticks[int(k)]
            out.append((tick, int(rest[0]), interval.get(tick)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subsystem")
    ap.add_argument("--run", type=pathlib.Path,
                    default=ROOT / "build" / "oracle" / "attract_boundaries" / "run1")
    ap.add_argument("--mutate", nargs=3, metavar=("FILE", "OLD", "NEW"),
                    help="check a mutant: replace OLD by NEW in port/FILE (must diverge)")
    args = ap.parse_args()
    r = check(args.subsystem, args.run, tuple(args.mutate) if args.mutate else None)
    print(r)
    if args.mutate:
        sys.exit(0 if not r["equivalent"] else 1)
    sys.exit(0 if r["equivalent"] else 1)


if __name__ == "__main__":
    main()
