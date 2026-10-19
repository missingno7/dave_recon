"""Deterministic behavioural oracle: run the ORIGINAL DAVE.EXE and record it.

The original executable is the behavioural reference for the native port
(docs/FIDELITY.md). This harness runs it in the pinned, emulated-time
instrumented DOSBox-X ("acceptance" build; C:/tools/CATALOG.md) with fixed
CPU cycles, a pinned DOS date/time, pristine copies of the game files, and a
scripted input schedule, and records:

  ticks           the complete live DGROUP (DS:0x0000-0x9F20) at the head of
                  every main-loop iteration (cs 0x0283, main's `call F_09DE`),
                  i.e. once per game tick, with its emulated time;
  sound requests  every call of PlaySound(n) (asm F_763E) with its id n,
                  assigned to the game tick it happened in;
  pit/speaker     the raw PIT (40h-43h) / speaker (61h) port stream;
  frames          the VGA framebuffer (A000:0000, 64000 bytes, mode 13h) at
                  every tick, sampled together with the state (the image the
                  previous tick left on screen); PNGs every N ticks.

Equivalence contract (docs/FIDELITY.md, verified by --repeat):
  * gameplay state: per-tick DGROUP equal EXCEPT the asynchronous PC-speaker
    driver variables DS [0x1384,0x1392) (INT 8 runs on its own PIT clock, so
    their value at the sampling instant depends on PIT phase, not on the game);
  * tick timing: per-tick intervals equal in whole vertical-retrace periods,
    except the interval after a title-screen tick (that timeout is measured
    on the asynchronous timer);
  * sound: the sequence of (tick, sound id) requests equal; the raw port
    stream is kept for analysis but not part of the contract;
  * frames: per-tick framebuffer byte-equal.

Scenario files (tests/oracle/*.txt):
  duration <ms>                     run length (emulated, from DOSBox start)
  png_every <n>                     write a PNG of every n-th tick's framebuffer
  <ms> key|keydown|keyup <name>     input (DOSBox-X mapper key names)

Usage:  python tools/oracle.py tests/oracle/attract.txt [--repeat 2]
Output: build/oracle/<scenario>/run<N>/{ticks.bin,ticks.jsonl,sounds.jsonl,
        pit.log,frame_*.png,summary.json}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DOSBOX = pathlib.Path(os.environ.get(
    "DAVE_ORACLE_DOSBOX", "C:/tools/dosbox-x-2026.08.31-simant-acceptance/dosbox-x-v3.exe"))
DOSBOX_SHA256 = "e5b9a81acb208bab48cb01a7dac9691cd06674fac877abce54e4693ece6dbff9"

LOAD_SEG = 0x0824             # measured; re-derived by calibrate() on every run
DGROUP_PARA = 0x254D
MAIN_LOOP_HEAD_CS = 0x0283    # main(): `call F_09DE`, first call of the per-tick pipeline
PLAYSOUND_CS = 0x743E         # lowlevel.asm _PlaySound (census F_763E)
# main()'s per-tick pipeline: the state at each call site is the state BEFORE
# that subsystem runs (and after the previous one); 0x2AA is the end of tick
# (`cmp [game_over],0`). Boundary snapshots let each native subsystem be
# verified in isolation (PORT_ROADMAP M1.2).
PIPELINE = [(0x283, "attract_mode"), (0x286, "process_input"), (0x289, "move_dave"),
            (0x28C, "update_explosions"), (0x28F, "move_monsters"), (0x292, "move_bullets"),
            (0x295, "animate_tiles"), (0x298, "check_collisions"), (0x29B, "pick_up_items"),
            (0x29E, "level_complete"), (0x2A1, "check_warp_transition"),
            (0x2A4, "update_jetpack"), (0x2A7, "handle_death"), (0x2AA, "end_of_tick")]
DGROUP_LIVE_LEN = 0x9F20      # DS 0 .. _STACK (docs/data-layout.md)
ASYNC_RANGES = [(0x1384, 0x1392)]   # INT 8 sound driver: TickDivide..SavedRate
CYCLES = 20000
LAUNCH_MS = 3000              # emulated time at which "DAVE<enter>" is typed
VBL_MS = 1000 / 70.086        # mode 13h vertical refresh in this emulation
TIME_TOLERANCE_MS = 0.01

FIELDS = {   # decoded into ticks.jsonl; names: docs/UNDERSTANDING_LEDGER.md
    "game_state": (0x00AA, 2, False),     # 0 play, 1 demo, 2 high scores, 3 title
    "score": (0x4C60, 4, False),
    "lives": (0x56EE, 2, True),
    "level": (0x56F4, 2, True),
    "player_x": (0x56EA, 2, True),
    "player_y": (0x56EC, 2, True),
    "view_column": (0x57A0, 2, True),
    "dave_state": (0x6156, 2, False),
    "game_over": (0x5792, 2, False),
    "has_gun": (0x4F84, 2, False),
    "got_trophy": (0x4F88, 2, False),
    "has_jetpack": (0x4F8A, 2, False),
    "jetpack_fuel": (0x5798, 2, False),
    "demo_mode": (0x9EC2, 2, False),      # 0 live, 1 playback, 2 record
    "demo_pos": (0x57A2, 2, False),
    "video_mode": (0x8B32, 2, False),
}


def decode(snapshot: bytes) -> dict:
    return {name: int.from_bytes(snapshot[off:off + w], "little", signed=s)
            for name, (off, w, s) in FIELDS.items()}


def gameplay_view(snapshot: bytes) -> bytes:
    b = bytearray(snapshot)
    for lo, hi in ASYNC_RANGES:
        b[lo:hi] = bytes(hi - lo)
    return bytes(b)


def parse_scenario(path: pathlib.Path):
    duration, frames, inputs = None, 0, []
    global BOUNDARY_TICKS
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if parts[0] == "duration":
            duration = int(parts[1])
        elif parts[0] == "png_every":
            frames = int(parts[1])
        elif parts[0] == "boundaries":
            BOUNDARY_TICKS = int(parts[1])
        elif len(parts) == 3 and parts[1] in ("key", "keydown", "keyup"):
            inputs.append(f"{int(parts[0])} {parts[1]} {parts[2]}")
        else:
            raise SystemExit(f"{path}:{n}: cannot parse {raw!r}")
    if duration is None:
        raise SystemExit(f"{path}: missing 'duration'")
    return duration, frames, inputs


def run_once(work: pathlib.Path, duration: int, frames, inputs, calibrate=False):
    if work.exists():
        shutil.rmtree(work)
    game = work / "game"
    game.mkdir(parents=True)
    for name in ("DAVE.EXE", "EGADAVE.DAV", "DSCORES.DAV"):
        if (ROOT / "assets" / name).exists():
            shutil.copyfile(ROOT / "assets" / name, game / name)
    ds_linear = (LOAD_SEG + DGROUP_PARA) * 16
    # DAVE is started by typing its name at a fixed EMULATED time rather than
    # from the autoexec, whose duration varies by ~1 ms with the host.
    lines = [f"{LAUNCH_MS + 100 * k} key {c}" for k, c in enumerate("dave")]
    lines.append(f"{LAUNCH_MS + 400} key enter")
    if calibrate:
        lines.append(f"{LAUNCH_MS + 1500} dump 0 a0000 mem.bin")
        lines.append(f"{LAUNCH_MS + 1600} exit")
    else:
        lines.append(f"0 on_exec {LOAD_SEG:04x}:{MAIN_LOOP_HEAD_CS:04x} 1000000 dump "
                     f"{ds_linear:x} {DGROUP_LIVE_LEN:x} tick")
        lines.append(f"0 on_exec {LOAD_SEG:04x}:{PLAYSOUND_CS:04x} 1000000 dump ss:sp+2 2 snd")
        lines.append("0 io_watch 40 43 pit.log out")
        lines.append("0 io_watch 61 61 pit.log inout")
        lines.append(f"0 on_exec {LOAD_SEG:04x}:{MAIN_LOOP_HEAD_CS:04x} 1000000 dump a0000 fa00 fb")
        if BOUNDARY_TICKS:
            for cs, _ in PIPELINE[1:]:    # PIPELINE[0] is the per-tick snapshot itself
                lines.append(f"0 on_exec {LOAD_SEG:04x}:{cs:04x} {BOUNDARY_TICKS} dump "
                             f"{ds_linear:x} {DGROUP_LIVE_LEN:x} b{cs:04x}")
        lines += inputs
        lines.append(f"{duration} exit")
    (work / "script.txt").write_text("\n".join(lines) + "\n")
    (work / "oracle.conf").write_text(
        "[sdl]\noutput=surface\n"
        "[dosbox]\nmachine=svga_s3\nmemsize=4\nworking directory option=noprompt\n"
        "synchronize time=false\n"
        f"acceptance script={work / 'script.txt'}\n"
        f"[cpu]\ncore=normal\ncputype=386\ncycles=fixed {CYCLES}\n"
        "[mixer]\nnosound=true\n"
        "[autoexec]\n"
        # The host clock must not leak in (C0S reads it; the game seeds its RNG
        # from time()): pin the emulated date and time.
        f'mount c "{game}"\nc:\nDATE 01/01/1991\nTIME 00:00:00\n')
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    subprocess.run([str(DOSBOX), "-conf", str(work / "oracle.conf"), "-noconsole"],
                   cwd=work, env=env, capture_output=True, timeout=600 + duration // 50)


def calibrate(out: pathlib.Path) -> int:
    run_once(out / "calibrate", 0, [], [], calibrate=True)
    mem = (out / "calibrate" / "mem.bin").read_bytes()
    lm = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()[0x200:]
    at = mem.find(lm[0x239:0x239 + 32])
    if at < 0:
        raise SystemExit("calibration: main() not found in memory (did DAVE start?)")
    return (at - 0x239) // 16


def _hits(work: pathlib.Path, prefix: str):
    i = 1
    while (work / f"{prefix}.{i}.bin").exists():
        b = (work / f"{prefix}.{i}.bin").read_bytes()
        meta = json.loads((work / f"{prefix}.{i}.json").read_text())
        (work / f"{prefix}.{i}.bin").unlink()
        (work / f"{prefix}.{i}.json").unlink()
        yield b, meta["emulated_ms"]
        i += 1


BOUNDARY_TICKS = 0      # set by a scenario's `boundaries <n>` line


def write_boundaries(work: pathlib.Path, tick_snapshots: list) -> int:
    """boundaries.bin: for each tick (up to BOUNDARY_TICKS) and each PIPELINE
    site in order, the DGROUP snapshot as zlib(snapshot XOR previous snapshot
    in the stream), framed as <u32 tick><u16 site index><u32 length><data>."""
    import struct
    import zlib
    per_site = {cs: [b for b, _ in _hits(work, f"b{cs:04x}")] for cs, _ in PIPELINE[1:]}
    n = min([len(tick_snapshots)] + [len(v) for v in per_site.values()])
    prev = bytes(DGROUP_LIVE_LEN)
    with open(work / "boundaries.bin", "wb") as f:
        for t in range(n):
            for i, (cs, _) in enumerate(PIPELINE):
                snap = tick_snapshots[t] if i == 0 else per_site[cs][t]
                delta = zlib.compress(bytes(a ^ b for a, b in zip(snap, prev)), 6)
                f.write(struct.pack("<IHI", t + 1, i, len(delta)) + delta)
                prev = snap
    return n


def iter_boundaries(path: pathlib.Path):
    """Yield (tick, site_name, snapshot) from a boundaries.bin (see above)."""
    import struct
    import zlib
    data = path.read_bytes()
    at, prev = 0, bytes(DGROUP_LIVE_LEN)
    while at < len(data):
        tick, site, length = struct.unpack_from("<IHI", data, at)
        at += 10
        snap = bytes(a ^ b for a, b in zip(zlib.decompress(data[at:at + length]), prev))
        at += length
        prev = snap
        yield tick, PIPELINE[site][1], snap


def collect(work: pathlib.Path, png_every: int = 0) -> dict:
    ticks, blob, game_blob = [], bytearray(), bytearray()
    for b, ms in _hits(work, "tick"):
        t0 = ticks[0]["emulated_ms"] if ticks else ms
        prev = ticks[-1] if ticks else None
        rec = {"tick": len(ticks) + 1, "emulated_ms": round(ms, 6), "t_ms": round(ms - t0, 6),
               "frames_since_prev": round((ms - prev["emulated_ms"]) / VBL_MS) if prev else 0,
               "sha1": hashlib.sha1(b).hexdigest(),
               "gameplay_sha1": hashlib.sha1(gameplay_view(b)).hexdigest()}
        rec.update(decode(b))
        ticks.append(rec)
        blob += b
        game_blob += gameplay_view(b)
    (work / "ticks.bin").write_bytes(bytes(blob))
    boundary_ticks = 0
    if BOUNDARY_TICKS:
        L = DGROUP_LIVE_LEN
        boundary_ticks = write_boundaries(work, [bytes(blob[k * L:(k + 1) * L])
                                                 for k in range(len(ticks))])
    (work / "ticks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ticks))

    sounds = []
    times = [r["emulated_ms"] for r in ticks]
    for b, ms in _hits(work, "snd"):
        k = sum(1 for t in times if t <= ms)          # tick in which PlaySound ran
        sounds.append({"tick": k, "sound": int.from_bytes(b, "little")})
    (work / "sounds.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sounds))

    import pixels
    pal = pixels.vga_palette((ROOT / "build" / "DAVE_unpacked.exe").read_bytes())
    frame_hashes = []
    for k, (data, _) in enumerate(_hits(work, "fb"), 1):
        frame_hashes.append(hashlib.sha1(data[:64000]).hexdigest())
        if png_every and k % png_every == 0:
            pixels.write_png([list(data[y * 320:(y + 1) * 320]) for y in range(200)],
                             work / f"tick{k:05d}.png", pal)
    (work / "frames.txt").write_text("".join(f"{h}\n" for h in frame_hashes))
    summary = {
        "ticks": len(ticks),
        "gameplay_sha1": hashlib.sha1(game_blob).hexdigest(),
        "sound_requests": len(sounds),
        "sound_requests_sha1": hashlib.sha1(json.dumps(sounds).encode()).hexdigest(),
        "pit_events": (work / "pit.log").read_text().count("\n") if (work / "pit.log").exists() else 0,
        "frames": len(frame_hashes),
        "frames_sha1": hashlib.sha1("".join(frame_hashes).encode()).hexdigest(),
        "boundary_ticks": boundary_ticks,
    }
    (work / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def compare_runs(a: pathlib.Path, b: pathlib.Path) -> list:
    """The equivalence contract above; returns problems, earliest divergence first."""
    problems = []
    ta = [json.loads(l) for l in (a / "ticks.jsonl").read_text().splitlines()]
    tb = [json.loads(l) for l in (b / "ticks.jsonl").read_text().splitlines()]
    for x, y in zip(ta, tb):
        if x["gameplay_sha1"] != y["gameplay_sha1"]:
            named = {k: (x[k], y[k]) for k in FIELDS if x[k] != y[k]}
            problems.append(f"gameplay state diverges at tick {x['tick']}: {named or 'unnamed bytes'}")
            break
        after_title = x["tick"] > 1 and ta[x["tick"] - 2]["game_state"] == 3
        if x["frames_since_prev"] != y["frames_since_prev"] and not after_title:
            problems.append(f"tick {x['tick']}: {x['frames_since_prev']} vs "
                            f"{y['frames_since_prev']} retraces since previous tick")
            break
    sa = (a / "sounds.jsonl").read_text().splitlines()
    sb = (b / "sounds.jsonl").read_text().splitlines()
    n = min(len(ta), len(tb))
    sa = [s for s in sa if json.loads(s)["tick"] < n]
    sb = [s for s in sb if json.loads(s)["tick"] < n]
    for i, (x, y) in enumerate(zip(sa, sb), 1):
        if x != y:
            problems.append(f"sound request {i}: {x} vs {y}")
            break
    if len(sa) != len(sb):
        problems.append(f"sound request count {len(sa)} vs {len(sb)} within the common {n} ticks")
    fa = (a / "frames.txt").read_text().split()
    fb = (b / "frames.txt").read_text().split()
    for k, (x, y) in enumerate(zip(fa, fb), 1):
        if x != y:
            problems.append(f"framebuffer differs at tick {k}")
            break
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", type=pathlib.Path)
    ap.add_argument("--repeat", type=int, default=1, help="runs; >1 checks the contract between them")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()
    if hashlib.sha256(DOSBOX.read_bytes()).hexdigest() != DOSBOX_SHA256:
        raise SystemExit(f"{DOSBOX} is not the pinned acceptance build")
    out = args.out or ROOT / "build" / "oracle" / args.scenario.stem
    seg = calibrate(out)
    if seg != LOAD_SEG:
        raise SystemExit(f"load segment moved: {seg:#x} != {LOAD_SEG:#x}; update LOAD_SEG")
    duration, frames, inputs = parse_scenario(args.scenario)
    for r in range(1, args.repeat + 1):
        run_once(out / f"run{r}", duration, frames, inputs)
        s = collect(out / f"run{r}", frames)
        print(f"run{r}: {s['ticks']} ticks, {s['sound_requests']} sound requests, "
              f"{s['pit_events']} PIT/speaker events, {s['frames']} frames, "
              f"gameplay {s['gameplay_sha1'][:12]}")
    if args.repeat > 1:
        problems = [p for r in range(2, args.repeat + 1)
                    for p in compare_runs(out / "run1", out / f"run{r}")]
        for p in problems:
            print("  " + p)
        print("EQUIVALENT (contract holds)" if not problems else "NOT EQUIVALENT")
        sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
