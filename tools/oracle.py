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
  rng seeds       every srand(seed) call (CS.LIB _srand, cs 0x9A38) with its
                  tick: the attract demo choice (srand(time)) and load_level's
                  srand(100);
  pit/speaker     the raw PIT (40h-43h) / speaker (61h) port stream;
  frames          the video memory at every tick, sampled together with the
                  state (the image the previous tick left on screen); PNGs
                  every N ticks. VGA mode 13h: A000:0000, 64000 bytes. CGA
                  mode 4: B800:0000, 16 KB (two interleaved banks). EGA mode
                  0Dh: A000:0000, 8000 bytes of ONE bit plane (the plane the
                  graphics controller's read map selects at that instant; a
                  CPU read of planar memory cannot see the others), plus the
                  true 4-plane image wherever the game itself selects each
                  plane for reading (`ega_planes`, see below);
  files           the game directory after the run (DSCORES.DAV, demo saves):
                  name, size and SHA-1 of every file.

Equivalence contract (docs/FIDELITY.md, verified by --repeat):
  * gameplay state: per-tick DGROUP equal EXCEPT the asynchronous PC-speaker
    driver variables DS [0x1384,0x1392) (INT 8 runs on its own PIT clock, so
    their value at the sampling instant depends on PIT phase, not on the game);
  * tick timing: per-tick intervals equal in whole vertical-retrace periods,
    except the interval after a tick that waits for the asynchronous sound
    driver (WaitSound: title/high-score ticks, see TIMING_EXEMPT_STATES);
  * sound: the sequence of (tick, sound id) requests equal; the raw port
    stream is kept for analysis but not part of the contract;
  * frames: per-tick framebuffer byte-equal (and the 4-plane EGA captures);
  * persistence: every file of the game directory after the run equal.

Scenario files (tests/oracle/*.txt):
  duration <ms>                     run length (emulated, from DOSBox start)
  png_every <n>                     write a PNG of every n-th tick's framebuffer
  boundaries <n>                    per-subsystem snapshots for the first n ticks
  video vga|ega|cga                 emulated adapter (machine=svga_s3/ega/cga);
                                    the game's VideoID picks mode 13h/0Dh/4
  dos_time HH:MM:SS                 DOS start time (default 00:00:00; the
                                    attract demo choice is srand(time()))
  retraces <n>                      per-retrace capture (M1.6) for the first n
                                    retraces: DGROUP + BIOS key buffer at every
                                    WaitVBL exit, see RETRACE_SITE
  dscores none|user                 starting high-score file: none (default; the game
                                    writes its default table) or assets/DSCORES.DAV
  ega_planes <n>                    EGA only: capture up to n true 4-plane
                                    images (at SaveUnderEGA, see EGA_PLANE_SITE)
  <ms> key|keydown|keyup <name>     input (DOSBox-X mapper key names)

Usage:  python tools/oracle.py tests/oracle/attract.txt [--repeat 2]
        python tools/oracle.py --report build/oracle/attract/run1
Output: build/oracle/<scenario>/run<N>/{ticks.bin,ticks.jsonl,sounds.jsonl,
        seeds.jsonl,pit.log,frames.txt,tick*.png,summary.json,game/}
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
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DOSBOX = pathlib.Path(os.environ.get(
    "DAVE_ORACLE_DOSBOX", "C:/tools/dosbox-x-2026.08.31-simant-acceptance/dosbox-x-v3.exe"))
DOSBOX_SHA256 = "e5b9a81acb208bab48cb01a7dac9691cd06674fac877abce54e4693ece6dbff9"

LOAD_SEG = 0x0824             # measured; re-derived by calibrate() on every run
DGROUP_PARA = 0x254D
MAIN_LOOP_HEAD_CS = 0x0283    # main(): `call F_09DE`, first call of the per-tick pipeline
PLAYSOUND_CS = 0x743E         # lowlevel.asm _PlaySound (census F_763E)
SRAND_CS = 0x9A38             # CS.LIB _srand (docs/library-map.md)
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
TIME_TOLERANCE_MS = 0.01
# Ticks whose length includes a wait on the asynchronous PIT sound driver
# (WaitSound in show_high_scores) or on keyboard prompts: the interval after a
# title tick (game_state 3), and the interval that ends at a title tick (game
# over -> check_high_score). Their retrace count varies with the PIT phase.
TIMING_EXEMPT_STATES = (3,)

# Per adapter: DOSBox-X machine, video memory captured per tick (linear,
# length), nominal retrace period (measured, docs/FIDELITY.md section 1),
# the game's g_video_mode.
VIDEO = {
    "vga": {"machine": "svga_s3", "fb": (0xA0000, 0xFA00), "vbl_ms": 1000 / 70.086, "mode": 3},
    "ega": {"machine": "ega", "fb": (0xA0000, 0x2000), "vbl_ms": 1000 / 59.92, "mode": 2},
    "cga": {"machine": "cga", "fb": (0xB8000, 0x4000), "vbl_ms": 1000 / 59.92, "mode": 1},
}
VBL_MS = VIDEO["vga"]["vbl_ms"]     # kept for importers
# EGA true-colour capture: tiles.asm SaveUnderEGA, the instruction after the
# read-map `out` in @@plane (`mov cx,bp`, cs 0x8545). SaveUnderEGA only READS
# video memory, so the four dumps of its first line (planes 3,2,1,0, AH = plane,
# BL = lines left) are one consistent image of all four planes, taken where
# draw_dave saves the background under Dave.
EGA_PLANE_SITE = 0x8545
# Per-retrace observation (M1.6, docs/state-model.md D2): lowlevel.asm
# _WaitVBL (census F_7831, cs 0x7631) leaves its polling loop at cs 0x7640
# (`pop di`) right after port 3DAh bit 3 rose, once per retrace the game
# waits for. Captured there: DGROUP and the BIOS keyboard buffer
# (0040:001A head, 001C tail, 001E..003D ring) = the frame's input.
RETRACE_SITE = 0x7640
BIOS_KBD = (0x41A, 0x24)

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
    "input_recorder_mode": (0x9EC2, 2, False),  # dead input recorder (HARDWARE.C g_demo_state), always 0
    "demo_pos": (0x57A2, 2, False),
    "video_mode": (0x8B32, 2, False),
    "in_warp_zone": (0x573C, 2, False),
    "warp_return_level": (0x6152, 2, True),
    "level_done": (0x6158, 2, False),
    "death_timer": (0x6546, 2, True),     # g_bonus_timer: 300-tick countdown armed by the death explosion
    "input_dir": (0x57E2, 2, False),
    "dave_facing": (0x5740, 2, False),
}
KEYDOWN = 0x8A32              # int key_down[128], indexed by scan code
MONSTER_ACTIVE = 0x5742       # int active[4]


def decode(snapshot: bytes) -> dict:
    d = {name: int.from_bytes(snapshot[off:off + w], "little", signed=s)
         for name, (off, w, s) in FIELDS.items()}
    d["monsters_active"] = [int.from_bytes(snapshot[MONSTER_ACTIVE + 2 * i:MONSTER_ACTIVE + 2 * i + 2],
                                           "little") for i in range(4)]
    d["keys_down"] = [k for k in range(128) if snapshot[KEYDOWN + 2 * k] | snapshot[KEYDOWN + 2 * k + 1]]
    return d


def gameplay_view(snapshot: bytes) -> bytes:
    b = bytearray(snapshot)
    for lo, hi in ASYNC_RANGES:
        b[lo:hi] = bytes(hi - lo)
    return bytes(b)


@dataclass
class Scenario:
    duration: int = 0
    png_every: int = 0
    boundaries: int = 0
    video: str = "vga"
    dos_time: str = "00:00:00"
    ega_planes: int = 0
    retraces: int = 0
    dscores: str = "none"     # "none": game writes its default table; "user": assets/DSCORES.DAV
    inputs: list = field(default_factory=list)


def parse_scenario(path: pathlib.Path) -> Scenario:
    sc, duration = Scenario(), None
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if parts[0] == "duration":
            duration = int(parts[1])
        elif parts[0] == "png_every":
            sc.png_every = int(parts[1])
        elif parts[0] == "boundaries":
            sc.boundaries = int(parts[1])
        elif parts[0] == "video" and len(parts) == 2 and parts[1] in VIDEO:
            sc.video = parts[1]
        elif parts[0] == "dos_time" and len(parts) == 2 and len(parts[1].split(":")) == 3:
            sc.dos_time = parts[1]
        elif parts[0] == "ega_planes":
            sc.ega_planes = int(parts[1])
        elif parts[0] == "retraces":
            sc.retraces = int(parts[1])
        elif parts[0] == "dscores" and len(parts) == 2 and parts[1] in ("none", "user"):
            sc.dscores = parts[1]
        elif len(parts) == 3 and parts[1] in ("key", "keydown", "keyup"):
            sc.inputs.append(f"{int(parts[0])} {parts[1]} {parts[2]}")
        else:
            raise SystemExit(f"{path}:{n}: cannot parse {raw!r}")
    if duration is None:
        raise SystemExit(f"{path}: missing 'duration'")
    if sc.ega_planes and sc.video != "ega":
        raise SystemExit(f"{path}: ega_planes needs 'video ega'")
    sc.duration = duration
    return sc


def run_once(work: pathlib.Path, sc: Scenario, calibrate=False):
    if work.exists():
        shutil.rmtree(work)
    game = work / "game"
    game.mkdir(parents=True)
    # The starting file set is pinned: the two hash-verified originals
    # (tools/bootstrap.py). DSCORES.DAV is user data (a high-score table, not
    # pinned), so by default it is absent and the game writes its default
    # table at start-up; `dscores user` opts in (its hash goes to summary.json).
    for name in ("DAVE.EXE", "EGADAVE.DAV"):
        shutil.copyfile(ROOT / "assets" / name, game / name)
    if sc.dscores == "user":
        shutil.copyfile(ROOT / "assets" / "DSCORES.DAV", game / "DSCORES.DAV")
    ds_linear = (LOAD_SEG + DGROUP_PARA) * 16
    fb_at, fb_len = VIDEO[sc.video]["fb"]
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
        lines.append(f"0 on_exec {LOAD_SEG:04x}:{SRAND_CS:04x} 1000000 dump ss:sp+2 2 seed")
        lines.append("0 io_watch 40 43 pit.log out")
        lines.append("0 io_watch 61 61 pit.log inout")
        lines.append(f"0 on_exec {LOAD_SEG:04x}:{MAIN_LOOP_HEAD_CS:04x} 1000000 dump "
                     f"{fb_at:x} {fb_len:x} fb")
        if sc.ega_planes:
            # every SaveUnderEGA plane read; collect() keeps the first line's 4
            lines.append(f"0 on_exec {LOAD_SEG:04x}:{EGA_PLANE_SITE:04x} {sc.ega_planes * 400} "
                         f"dump a0000 1f40 ep")
        if sc.retraces:
            lines.append(f"0 on_exec {LOAD_SEG:04x}:{RETRACE_SITE:04x} {sc.retraces} dump "
                         f"{ds_linear:x} {DGROUP_LIVE_LEN:x} r")
            lines.append(f"0 on_exec {LOAD_SEG:04x}:{RETRACE_SITE:04x} {sc.retraces} dump "
                         f"{BIOS_KBD[0]:x} {BIOS_KBD[1]:x} k")
        if sc.boundaries:
            for cs, _ in PIPELINE[1:]:    # PIPELINE[0] is the per-tick snapshot itself
                lines.append(f"0 on_exec {LOAD_SEG:04x}:{cs:04x} {sc.boundaries} dump "
                             f"{ds_linear:x} {DGROUP_LIVE_LEN:x} b{cs:04x}")
        lines += sc.inputs
        lines.append(f"{sc.duration} exit")
    (work / "script.txt").write_text("\n".join(lines) + "\n")
    (work / "oracle.conf").write_text(
        "[sdl]\noutput=surface\n"
        f"[dosbox]\nmachine={VIDEO[sc.video]['machine']}\nmemsize=4\n"
        "working directory option=noprompt\n"
        "synchronize time=false\n"
        f"acceptance script={work / 'script.txt'}\n"
        f"[cpu]\ncore=normal\ncputype=386\ncycles=fixed {CYCLES}\n"
        "[mixer]\nnosound=true\n"
        # frameskip=1: with 0, DOSBox-X's VGA vertical-timer drift compensation
        # (vga_draw.cpp VGA_VerticalTimer, vsync_adj) is fed by frame accounting
        # in the host rendering path and shifted the emulated retrace timeline
        # by whole frames between identical runs (docs/FIDELITY.md section 1).
        "[render]\nframeskip=1\n"
        "[autoexec]\n"
        # The host clock must not leak in (C0S reads it; the game seeds its RNG
        # from time()): pin the emulated date and time.
        f'mount c "{game}"\nc:\nDATE 01/01/1991\nTIME {sc.dos_time}\n')
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    subprocess.run([str(DOSBOX), "-conf", str(work / "oracle.conf"), "-noconsole"],
                   cwd=work, env=env, capture_output=True, timeout=900 + sc.duration // 20)


def calibrate(out: pathlib.Path, video: str = "vga") -> int:
    run_once(out / "calibrate", Scenario(video=video), calibrate=True)
    mem = (out / "calibrate" / "mem.bin").read_bytes()
    lm = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()[0x200:]
    at = mem.find(lm[0x239:0x239 + 32])
    if at < 0:
        raise SystemExit("calibration: main() not found in memory (did DAVE start?)")
    return (at - 0x239) // 16


def _hits(work: pathlib.Path, prefix: str, regs: bool = False):
    i = 1
    while (work / f"{prefix}.{i}.bin").exists():
        b = (work / f"{prefix}.{i}.bin").read_bytes()
        meta = json.loads((work / f"{prefix}.{i}.json").read_text())
        (work / f"{prefix}.{i}.bin").unlink()
        (work / f"{prefix}.{i}.json").unlink()
        yield (b, meta["emulated_ms"], meta["registers"]) if regs else (b, meta["emulated_ms"])
        i += 1


def _xor(a: bytes, b: bytes) -> bytes:
    """Byte-wise XOR of two equal-length buffers (fast: one big-int operation)."""
    n = len(a)
    return (int.from_bytes(a, "little") ^ int.from_bytes(b, "little")).to_bytes(n, "little")


def write_boundaries(work: pathlib.Path, tick_snapshots: list) -> int:
    """boundaries.bin: for each tick (up to the scenario's `boundaries`) and each
    PIPELINE site in order, the DGROUP snapshot as zlib(snapshot XOR previous
    snapshot in the stream), framed as <u32 tick><u16 site index><u32 length><data>."""
    import struct
    import zlib
    per_site = {cs: [b for b, _ in _hits(work, f"b{cs:04x}")] for cs, _ in PIPELINE[1:]}
    n = min([len(tick_snapshots)] + [len(v) for v in per_site.values()])
    prev = bytes(DGROUP_LIVE_LEN)
    with open(work / "boundaries.bin", "wb") as f:
        for t in range(n):
            for i, (cs, _) in enumerate(PIPELINE):
                snap = tick_snapshots[t] if i == 0 else per_site[cs][t]
                delta = zlib.compress(_xor(snap, prev), 6)
                f.write(struct.pack("<IHI", t + 1, i, len(delta)) + delta)
                prev = snap
    return n


def script_keys(sc: Scenario):
    """The scenario's key script as (ms, mapper name, down?) transitions, with
    `key` taps expanded the way the acceptance build does (50 ms; an
    upper-case letter is a 52 ms lshift chord)."""
    ev = []
    for line in sc.inputs:
        ms, kind, name = line.split()
        ms = int(ms)
        upper = len(name) == 1 and name.isupper()
        low = name.lower()
        if kind == "key":
            if upper:
                ev += [(ms, "lshift", True), (ms + 1, low, True), (ms + 51, low, False),
                       (ms + 52, "lshift", False)]
            else:
                ev += [(ms, low, True), (ms + 50, low, False)]
        elif upper:
            ev += [(ms, "lshift", True), (ms + 1, low, True)] if kind == "keydown" else \
                  [(ms + 1, low, False), (ms + 2, "lshift", False)]
        else:
            ev.append((ms, low, kind == "keydown"))
    return sorted(ev, key=lambda e: e[0])


def collect_retraces(work: pathlib.Path, sc: Scenario, times: list) -> int:
    """retraces.bin: per captured retrace <u32 index><u32 tick><f64 ms><u32 len>
    zlib(DGROUP XOR previous); retraces.jsonl: per retrace the tick it belongs
    to (number of tick heads <= its time), the gameplay hash, key_down[] and
    the pending BIOS keys as captured, and the keys the scenario script holds
    at that time (the per-frame input reconstruction)."""
    import bisect
    import struct
    import zlib
    kbd = [b for b, _ in _hits(work, "k")]
    script = script_keys(sc)
    held, si = set(), 0
    prev = bytes(DGROUP_LIVE_LEN)
    recs = []
    with open(work / "retraces.bin", "wb") as f:
        for i, (snap, ms) in enumerate(_hits(work, "r")):
            while si < len(script) and script[si][0] <= ms:
                _, name, down = script[si]
                (held.add if down else held.discard)(name)
                si += 1
            tick = bisect.bisect_right(times, ms)
            delta = zlib.compress(bytes(x ^ y for x, y in zip(snap, prev)), 6)
            f.write(struct.pack("<IIdI", i + 1, tick, ms, len(delta)) + delta)
            prev = snap
            buf = kbd[i] if i < len(kbd) else b""
            pending = []
            if len(buf) == BIOS_KBD[1]:
                head, tail = struct.unpack_from("<HH", buf, 0)
                while head != tail and len(pending) < 16:
                    off = head - 0x1A
                    if not 4 <= off < len(buf) - 1:
                        break
                    pending.append(struct.unpack_from("<H", buf, off)[0])
                    head = head + 2 if head + 2 < 0x3E else 0x1E
            recs.append({"retrace": i + 1, "tick": tick, "emulated_ms": round(ms, 6),
                         "gameplay_sha1": hashlib.sha1(gameplay_view(snap)).hexdigest(),
                         "keys_down": [k for k in range(128)
                                       if snap[KEYDOWN + 2 * k] | snap[KEYDOWN + 2 * k + 1]],
                         "bios_keys": pending, "script_keys": sorted(held)})
    (work / "retraces.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    return len(recs)


def iter_retraces(path: pathlib.Path):
    """Yield (index, tick, emulated_ms, DGROUP snapshot) from a retraces.bin."""
    import struct
    import zlib
    data = path.read_bytes()
    at, prev = 0, bytes(DGROUP_LIVE_LEN)
    while at < len(data):
        i, tick, ms, length = struct.unpack_from("<IIdI", data, at)
        at += 20
        snap = bytes(x ^ y for x, y in zip(zlib.decompress(data[at:at + length]), prev))
        at += length
        prev = snap
        yield i, tick, ms, snap


def iter_boundaries(path: pathlib.Path):
    """Yield (tick, site_name, snapshot) from a boundaries.bin (see above)."""
    import struct
    import zlib
    data = path.read_bytes()
    at, prev = 0, bytes(DGROUP_LIVE_LEN)
    while at < len(data):
        tick, site, length = struct.unpack_from("<IHI", data, at)
        at += 10
        snap = _xor(zlib.decompress(data[at:at + length]), prev)
        at += length
        prev = snap
        yield tick, PIPELINE[site][1], snap


# ------------------------------------------------------------- framebuffers

def frame_pixels(video: str, data: bytes):
    """Rows of palette indices for a PNG. EGA: one plane as a bit mask (0/15)."""
    if video == "vga":
        return [list(data[y * 320:(y + 1) * 320]) for y in range(200)]
    if video == "cga":
        rows = []
        for y in range(200):
            line = data[(y & 1) * 0x2000 + (y >> 1) * 80:][:80]
            rows.append([(b >> (6 - 2 * k)) & 3 for b in line for k in range(4)])
        return rows
    return [[15 if (b >> (7 - k)) & 1 else 0 for b in data[y * 40:(y + 1) * 40] for k in range(8)]
            for y in range(200)]


def ega_compose(planes) -> list:
    """Four 8000-byte bit planes (index = plane) -> rows of 4-bit colour indices."""
    rows = []
    for y in range(200):
        row = []
        for xb in range(40):
            p = [planes[k][y * 40 + xb] for k in range(4)]
            for bit in range(7, -1, -1):
                row.append(sum(((p[k] >> bit) & 1) << k for k in range(4)))
        rows.append(row)
    return rows


def palette_for(video: str):
    import pixels
    if video == "vga":
        return pixels.vga_palette((ROOT / "build" / "DAVE_unpacked.exe").read_bytes())
    if video == "cga":
        return pixels.CGA_PALETTE
    return pixels.ega_palette()


def collect_ega_planes(work: pathlib.Path, times: list, limit: int, png: bool) -> list:
    """Group SaveUnderEGA plane-read dumps into 4-plane images (first line of
    each call: AH = 3,2,1,0 with the same BL), assigned to ticks."""
    import pixels
    images, cur, prev_bl = [], None, None
    for data, ms, r in _hits(work, "ep", regs=True):
        eax, ebx = int(r["eax"], 16), int(r["ebx"], 16)
        plane, lines_left = (eax >> 8) & 0xFF, ebx & 0xFF
        if plane == 3:
            # a new line; it is the first line of a call unless the previous
            # line of the same call (BL one higher) came just before
            cur = {"ms": ms, "bl": lines_left, "first": prev_bl != lines_left + 1,
                   "planes": {3: data[:8000]}}
            prev_bl = lines_left
        elif cur is not None and cur["bl"] == lines_left and plane == min(cur["planes"]) - 1:
            cur["planes"][plane] = data[:8000]
            if plane == 0:
                if cur["first"] and len(images) < limit:
                    tick = sum(1 for t in times if t <= cur["ms"])
                    images.append((tick, [cur["planes"][k] for k in range(4)]))
                cur = None
        else:
            cur = None
    pal = pixels.ega_palette()
    records = []
    for n, (tick, planes) in enumerate(images, 1):
        sha = hashlib.sha1(b"".join(planes)).hexdigest()
        records.append({"capture": n, "tick": tick, "sha1": sha})
        if png:
            pixels.write_png(ega_compose(planes), work / f"ega{n:04d}_tick{tick:05d}.png", pal)
    (work / "ega_planes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    return records


def collect(work: pathlib.Path, sc: Scenario) -> dict:
    vbl = VIDEO[sc.video]["vbl_ms"]
    ticks, blob, game_blob = [], bytearray(), bytearray()
    for b, ms in _hits(work, "tick"):
        t0 = ticks[0]["emulated_ms"] if ticks else ms
        prev = ticks[-1] if ticks else None
        rec = {"tick": len(ticks) + 1, "emulated_ms": round(ms, 6), "t_ms": round(ms - t0, 6),
               "frames_since_prev": round((ms - prev["emulated_ms"]) / vbl) if prev else 0,
               "sha1": hashlib.sha1(b).hexdigest(),
               "gameplay_sha1": hashlib.sha1(gameplay_view(b)).hexdigest()}
        rec.update(decode(b))
        ticks.append(rec)
        blob += b
        game_blob += gameplay_view(b)
    (work / "ticks.bin").write_bytes(bytes(blob))
    boundary_ticks = 0
    if sc.boundaries:
        L = DGROUP_LIVE_LEN
        boundary_ticks = write_boundaries(work, [bytes(blob[k * L:(k + 1) * L])
                                                 for k in range(len(ticks))])
    (work / "ticks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ticks))

    times = [r["emulated_ms"] for r in ticks]
    sounds = []
    for b, ms in _hits(work, "snd"):
        k = sum(1 for t in times if t <= ms)          # tick in which PlaySound ran
        sounds.append({"tick": k, "sound": int.from_bytes(b, "little")})
    (work / "sounds.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sounds))
    seeds = []
    for b, ms in _hits(work, "seed"):
        seeds.append({"tick": sum(1 for t in times if t <= ms), "emulated_ms": round(ms, 3),
                      "seed": int.from_bytes(b, "little")})
    (work / "seeds.jsonl").write_text("".join(json.dumps(s) + "\n" for s in seeds))

    import pixels
    pal = palette_for(sc.video)
    frame_hashes = []
    for k, (data, _) in enumerate(_hits(work, "fb"), 1):
        frame_hashes.append(hashlib.sha1(data).hexdigest())
        if sc.png_every and k % sc.png_every == 0:
            pixels.write_png(frame_pixels(sc.video, data), work / f"tick{k:05d}.png", pal)
    (work / "frames.txt").write_text("".join(f"{h}\n" for h in frame_hashes))
    retraces = collect_retraces(work, sc, times) if sc.retraces else 0
    ega = collect_ega_planes(work, times, sc.ega_planes, bool(sc.png_every)) if sc.ega_planes else []

    files = {}
    for p in sorted((work / "game").iterdir()):
        if p.is_file():
            data = p.read_bytes()
            files[p.name] = {"size": len(data), "sha1": hashlib.sha1(data).hexdigest()}
    # mean retrace period over the play/demo ticks (title/high-score
    # intervals excluded): total time / total retraces
    span = [(a, b) for a, b in zip(ticks, ticks[1:])
            if a["game_state"] not in TIMING_EXEMPT_STATES and b["game_state"] != 3]
    span_frames = sum(b["frames_since_prev"] for _, b in span)
    span_ms = sum(b["emulated_ms"] - a["emulated_ms"] for a, b in span)
    summary = {
        "video": sc.video,
        "ticks": len(ticks),
        "gameplay_sha1": hashlib.sha1(game_blob).hexdigest(),
        "sound_requests": len(sounds),
        "sound_requests_sha1": hashlib.sha1(json.dumps(sounds).encode()).hexdigest(),
        "seeds": [s["seed"] for s in seeds],
        "pit_events": (work / "pit.log").read_text().count("\n") if (work / "pit.log").exists() else 0,
        "frames": len(frame_hashes),
        "frames_sha1": hashlib.sha1("".join(frame_hashes).encode()).hexdigest(),
        "ega_plane_captures": len(ega),
        "ega_planes_sha1": hashlib.sha1("".join(r["sha1"] for r in ega).encode()).hexdigest(),
        "boundary_ticks": boundary_ticks,
        "retraces": retraces,
        "retrace_ms_mean": round(span_ms / span_frames, 6) if span_frames else None,
        "files": files,
    }
    (work / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def compare_runs(a: pathlib.Path, b: pathlib.Path) -> list:
    """The equivalence contract above; returns problems, earliest divergence first."""
    problems = []
    ta = [json.loads(l) for l in (a / "ticks.jsonl").read_text().splitlines()]
    tb = [json.loads(l) for l in (b / "ticks.jsonl").read_text().splitlines()]
    if len(ta) != len(tb):
        problems.append(f"tick count {len(ta)} vs {len(tb)}")
    for x, y in zip(ta, tb):
        if x["gameplay_sha1"] != y["gameplay_sha1"]:
            named = {k: (x[k], y[k]) for k in FIELDS if x[k] != y[k]}
            problems.append(f"gameplay state diverges at tick {x['tick']}: {named or 'unnamed bytes'}")
            break
        # intervals starting at a title/high-score tick, or ending at a title
        # tick (game over -> high-score table and initials), contain WaitSound
        # and keyboard prompts: their retrace count is not part of the contract
        exempt = x["tick"] > 1 and (ta[x["tick"] - 2]["game_state"] in TIMING_EXEMPT_STATES
                                    or x["game_state"] == 3)
        if x["frames_since_prev"] != y["frames_since_prev"] and not exempt:
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
    if (a / "retraces.jsonl").exists() and (b / "retraces.jsonl").exists():
        problems += compare_retraces(a, b, ta)
    if (a / "ega_planes.jsonl").exists() or (b / "ega_planes.jsonl").exists():
        ea = (a / "ega_planes.jsonl").read_text().splitlines()
        eb = (b / "ega_planes.jsonl").read_text().splitlines()
        if ea != eb:
            k = next((i for i, (x, y) in enumerate(zip(ea, eb), 1) if x != y), min(len(ea), len(eb)) + 1)
            problems.append(f"EGA 4-plane capture {k} differs")
    fa = json.loads((a / "summary.json").read_text()).get("files", {})
    fb = json.loads((b / "summary.json").read_text()).get("files", {})
    for name in sorted(set(fa) | set(fb)):
        if fa.get(name) != fb.get(name):
            problems.append(f"game file {name} after the run: {fa.get(name)} vs {fb.get(name)}")
    return problems


def compare_retraces(a: pathlib.Path, b: pathlib.Path, ta: list) -> list:
    """Per-retrace contract (M1.6): within every tick whose interval is under
    the timing contract (see compare_runs), the sequence of per-retrace
    gameplay states and captured key tables must be equal."""
    ra = [json.loads(l) for l in (a / "retraces.jsonl").read_text().splitlines()]
    rb = [json.loads(l) for l in (b / "retraces.jsonl").read_text().splitlines()]
    n = min(ra[-1]["tick"] if ra else 0, rb[-1]["tick"] if rb else 0)

    def by_tick(rs):
        d = {}
        for r in rs:
            if r["tick"] < n:          # the last captured tick may be cut off
                d.setdefault(r["tick"], []).append((r["gameplay_sha1"], r["keys_down"]))
        return d
    da, db = by_tick(ra), by_tick(rb)
    for k in sorted(set(da) | set(db)):
        if 1 <= k < len(ta) and (ta[k - 1]["game_state"] in TIMING_EXEMPT_STATES
                                 or ta[k]["game_state"] == 3):
            continue
        if da.get(k) != db.get(k):
            sa, sb = da.get(k, []), db.get(k, [])
            j = next((j for j, (x, y) in enumerate(zip(sa, sb)) if x != y), min(len(sa), len(sb)))
            return [f"per-retrace state differs in tick {k} at retrace {j + 1} ({len(sa)} vs {len(sb)} retraces)"]
    return []


def report(run: pathlib.Path) -> str:
    """Tick ranges of constant (game_state, level, in_warp_zone), with the
    demo index for demo segments: the evidence lines for scenario headers."""
    import demos
    import far_data
    bank = demos.decode(far_data.segment_bytes(far_data.DEFAULT_EXE.read_bytes(), demos.SEGMENT))
    import struct
    blob = far_data.segment_bytes(far_data.DEFAULT_EXE.read_bytes(), demos.SEGMENT)
    offsets = list(struct.unpack_from(f"<{len(bank['demos'])}I", blob, 4))
    ticks = [json.loads(l) for l in (run / "ticks.jsonl").read_text().splitlines()]
    out, start = [], 0
    names = {0: "play", 1: "demo", 2: "high scores", 3: "title"}

    def key(t):
        return (t["game_state"], t["level"], t["in_warp_zone"])

    for i in range(1, len(ticks) + 1):
        if i == len(ticks) or key(ticks[i]) != key(ticks[start]):
            a, b = ticks[start], ticks[i - 1]
            desc = f"ticks {a['tick']}-{b['tick']}: {names.get(a['game_state'], a['game_state'])}"
            if a["game_state"] in (0, 1):
                desc += f", level {a['level'] + 1} (index {a['level']})"
                if a["in_warp_zone"]:
                    desc += " warp zone"
            if a["game_state"] == 1:
                pos = a["demo_pos"]
                idx = max((k for k, o in enumerate(offsets) if o < pos), default=None)
                desc += f", demo {idx}"
            desc += (f"; score {a['score']}->{b['score']}, lives {a['lives']}->{b['lives']}"
                     f", t {a['emulated_ms'] / 1000:.2f}-{b['emulated_ms'] / 1000:.2f} s")
            out.append(desc)
            start = i
    return "\n".join(out)


def snap_scenario(path: pathlib.Path, run: pathlib.Path) -> int:
    """Move every input event of a scenario to the middle of the sampling
    window it fell into in `run` (a run of this same scenario), so the tick that
    samples it does not depend on the emulator's retrace-phase jitter
    (docs/FIDELITY.md section 1). An event at T is sampled by the first tick
    whose head is >= T (process_input runs right after the head):
      * one-retrace window (head_{n-1}, head_n]: T' = its midpoint;
      * a longer tick (scrolling, death/level/warp sequences, title,
        wait_for_input): the LAST event before head_n goes to head_n -
        min(10.5 retraces, gap/2), the middle of wait_for_input's 20-retrace
        poll period and half a retrace off its polls;
        other events inside that tick are blocking-prompt keys (title, high-score
        initials) and are left where the author put them.
    If the run has a per-retrace capture (`retraces`), every event instead goes
    to the middle of the two WaitVBL exits around it, which also makes the
    per-retrace input reproducible.
    The per-tick input of the snapped scenario equals the draft's, so the draft
    run's tick times stay valid. Rewrites the file in place; returns the number
    of events moved."""
    sc = parse_scenario(path)
    vbl = VIDEO[sc.video]["vbl_ms"]
    heads = [json.loads(l)["emulated_ms"] for l in (run / "ticks.jsonl").read_text().splitlines()]
    lines = path.read_text().splitlines()
    events = []
    for i, raw in enumerate(lines):
        parts = raw.split("#", 1)[0].split()
        if len(parts) == 3 and parts[1] in ("key", "keydown", "keyup"):
            events.append((i, int(parts[0])))
    import bisect
    moved = 0
    if (run / "retraces.jsonl").exists():
        # Retrace-level snapping (M1.6 capture): every key/BIOS sample the game
        # takes happens right after a WaitVBL exit, so the middle between the
        # two retraces around T keeps T's sampling point and is half a
        # retrace away from any sample.
        rt = [json.loads(l)["emulated_ms"] for l in (run / "retraces.jsonl").read_text().splitlines()]
        for i, t in events:
            n = bisect.bisect_left(rt, t)
            if 0 < n < len(rt):
                t_new = int(round((rt[n - 1] + rt[n]) / 2))
                code, _, comment = lines[i].partition("#")
                parts = code.split()
                if int(parts[0]) != t_new:
                    moved += 1
                lines[i] = f"{t_new} {parts[1]} {parts[2]}" + (f"  #{comment}" if comment else "")
        path.write_text("\n".join(lines) + "\n")
        return moved
    groups = {}
    for i, t in events:
        n = bisect.bisect_left(heads, t)          # heads[n] >= t
        if 0 < n < len(heads):
            groups.setdefault(n, []).append((i, t))
    for n, evs in groups.items():
        gap = heads[n] - heads[n - 1]
        if gap < 1.5 * vbl:
            targets = [(i, heads[n - 1] + gap / 2) for i, _ in evs]
        else:
            last_t = max(t for _, t in evs)
            targets = [(i, heads[n] - min(10.5 * vbl, gap / 2)) for i, t in evs if t == last_t]
        for i, t_new in targets:
            raw = lines[i]
            code, _, comment = raw.partition("#")
            parts = code.split()
            new = f"{int(round(t_new))} {parts[1]} {parts[2]}"
            if int(parts[0]) != int(round(t_new)):
                moved += 1
            lines[i] = new + (f"  #{comment}" if comment else "")
    path.write_text("\n".join(lines) + "\n")
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", type=pathlib.Path, nargs="?")
    ap.add_argument("--repeat", type=int, default=1, help="runs; >1 checks the contract between them")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--report", type=pathlib.Path, default=None, metavar="RUN_DIR",
                    help="print the tick ranges of a collected run and exit")
    ap.add_argument("--snap", action="store_true",
                    help="after the run(s), move the scenario's input events to the middle "
                         "of their sampling windows (rewrites the scenario file)")
    args = ap.parse_args()
    if args.report:
        print(report(args.report))
        return
    if args.scenario is None:
        ap.error("a scenario is required")
    if hashlib.sha256(DOSBOX.read_bytes()).hexdigest() != DOSBOX_SHA256:
        raise SystemExit(f"{DOSBOX} is not the pinned acceptance build")
    # absolute: DOSBox runs in the run directory, a relative path would hang it
    out = (args.out or ROOT / "build" / "oracle" / args.scenario.stem).resolve()
    sc = parse_scenario(args.scenario)
    seg = calibrate(out, sc.video)
    if seg != LOAD_SEG:
        raise SystemExit(f"load segment moved: {seg:#x} != {LOAD_SEG:#x}; update LOAD_SEG")
    for r in range(1, args.repeat + 1):
        run_once(out / f"run{r}", sc)
        s = collect(out / f"run{r}", sc)
        print(f"run{r}: {s['ticks']} ticks, {s['sound_requests']} sound requests, "
              f"{s['pit_events']} PIT/speaker events, {s['frames']} frames, "
              f"gameplay {s['gameplay_sha1'][:12]}, files "
              + ", ".join(f"{k} {v['sha1'][:8]}" for k, v in s["files"].items()))
    if args.snap:
        print(f"snapped {snap_scenario(args.scenario, out / 'run1')} input events in {args.scenario}")
    if args.repeat > 1:
        problems = [p for r in range(2, args.repeat + 1)
                    for p in compare_runs(out / "run1", out / f"run{r}")]
        for p in problems:
            print("  " + p)
        print("EQUIVALENT (contract holds)" if not problems else "NOT EQUIVALENT")
        sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
