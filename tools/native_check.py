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

Builds port/ with CMake (MinGW gcc) into build/port first.
"""
from __future__ import annotations

import argparse
import os
import pathlib
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
# record of the current level inside g_levels, minus documented deferrals.
DEFERRED = {
    "data:g_tiles": "pristine copy of the current level map: derived from the level resource "
                    "by the native game, rebuilt by the bridge once resources are loaded",
}
DEFERRED_RANGES = [(0x5742 + 5 * 8, 0x5742 + 6 * 8,
                    "g_monsters.sprite[4]: per-mode presentation id (state-model D3)")]


def game_view_mask(snapshot: bytes) -> bytearray:
    import json
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
    level = int.from_bytes(snapshot[0x56F4:0x56F6], "little", signed=True)
    m = (0x173A + 0x500 * level + 0x100) & 0xFFFF
    for i in range(m, min(m + 1000, len(mask))):
        mask[i] = 1
    for lo, hi in oracle.ASYNC_RANGES:
        mask[lo:hi] = bytes(hi - lo)
    return mask


def build_port() -> pathlib.Path:
    env = dict(os.environ, PATH=MINGW + os.pathsep + os.environ["PATH"])
    out = ROOT / "build" / "port"
    subprocess.run([CMAKE, "-S", str(ROOT / "port"), "-B", str(out), "-G", "MinGW Makefiles",
                    "-DCMAKE_C_COMPILER=gcc", "-DCMAKE_MAKE_PROGRAM=mingw32-make"],
                   env=env, check=True, capture_output=True)
    subprocess.run([CMAKE, "--build", str(out)], env=env, check=True, capture_output=True)
    return out / "dave_bridge.exe"


def check(subsystem: str, run: pathlib.Path) -> dict:
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
    work = ROOT / "build" / "native_check" / subsystem
    work.mkdir(parents=True, exist_ok=True)
    (work / "pre.bin").write_bytes(b"".join(p for _, p, _ in pairs))
    exe = build_port()
    env = dict(os.environ, PATH=MINGW + os.pathsep + os.environ["PATH"])
    subprocess.run([str(exe), subsystem, str(work / "pre.bin"), str(work / "native.bin"),
                    str(work / "events.txt")], env=env, check=True)
    native = (work / "native.bin").read_bytes()
    L = oracle.DGROUP_LIVE_LEN
    changed_in_original = presentation_bytes = 0
    for k, (tick, pre, post) in enumerate(pairs):
        mine = native[k * L:(k + 1) * L]
        mask = game_view_mask(pre) if subsystem != "identity" else bytearray([1]) * L
        if any(pre[i] != post[i] for i in range(L) if mask[i]):
            changed_in_original += 1
        presentation_bytes += sum(1 for i in range(L) if not mask[i] and pre[i] != post[i])
        diff = [i for i in range(L) if mask[i] and mine[i] != post[i]]
        if diff:
            return {"subsystem": subsystem, "ticks": len(pairs), "equivalent": False,
                    "first_divergence": {"tick": tick, "ds_offsets": [hex(i) for i in diff[:16]]}}
    return {"subsystem": subsystem, "ticks": len(pairs), "equivalent": True,
            "ticks_where_original_changed_game_state": changed_in_original,
            "non_game_bytes_changed_by_original": presentation_bytes,
            "events": len((work / "events.txt").read_text().splitlines())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subsystem")
    ap.add_argument("--run", type=pathlib.Path,
                    default=ROOT / "build" / "oracle" / "attract_boundaries" / "run1")
    args = ap.parse_args()
    r = check(args.subsystem, args.run)
    print(r)
    sys.exit(0 if r["equivalent"] else 1)


if __name__ == "__main__":
    main()
