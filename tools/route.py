"""Scripted-route tooling for the oracle corpus (docs/FIDELITY.md section 5).

Long keyboard routes (levels 2-5, warps, the jetpack) are impractical to
write by hand in emulated milliseconds. This module plans them per TICK with
a fast simulator and turns the plan into scenario key events; the ORIGINAL
(tools/oracle.py) stays the judge: every planned segment is run on DAVE.EXE,
snapped (`--snap`, retraces capture) and must pass `--repeat 2`.

  * `Sim` drives tools/route_sim.c: the native port's pipeline calls chained
    from one original DGROUP snapshot (a tick head of an oracle run), one
    constant input per tick, with save/load slots for search.
  * `search` is a best-first search (fewest ticks) over "macro" moves from
    standing positions (walk n ticks, jump N/NE/NW with air control, climb,
    jetpack flight) until a goal predicate holds; deaths are pruned.
  * `events` converts per-tick inputs into `keydown`/`keyup` events in the
    middle of the retrace before each tick head (tick-head times from the
    oracle run where it has them, else extended with the simulator's retrace
    counts); a waiting loop the input does not end at its first poll gets its
    key just before that poll (`first_poll`).
  * `replay_check` re-simulates an oracle run's ticks from its own key tables
    and reports the first tick where the simulator disagrees: the planner is
    only trusted where this holds.

    python tools/route.py check RUN_DIR [--from TICK] [--to TICK]
    python tools/route.py sim RUN_DIR TICK "2x30 1/j 8x40"     (quick what-if)

Direction keys (default bindings g_key_scans, DS 0x1310): N up, NE pageup,
E right, SE pagedown, S down, SW end, W left, NW home; fire Ctrl, jump/jetpack
Alt. Each direction is ONE key, so a direction change is one keyup plus one
keydown at the same time.
"""
from __future__ import annotations

import argparse
import heapq
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import oracle  # noqa: E402

MINGW = os.environ.get("DAVE_MINGW_BIN", "C:/msys64/mingw64/bin")
SIM_EXE = ROOT / "build" / "route_sim.exe"
DIR_KEYS = {0: "up", 1: "pageup", 2: "right", 3: "pagedown", 4: "down", 5: "end", 6: "left", 7: "home"}
FIRE_KEY, JUMP_KEY = "lctrl", "lalt"
# key_down[] scan codes of the default bindings: N, NE, E, SE, S, SW, W, NW, fire, jump
DEFAULT_SCANS = [0x48, 0x49, 0x4D, 0x51, 0x50, 0x4F, 0x4B, 0x47, 0x1D, 0x38]
FIELDS = ["retraces", "x", "y", "state", "level", "scroll", "score", "lives", "trophy", "jetpack",
          "fuel", "gun", "done", "warp", "mode", "game_over", "death_timer", "first_poll",
          "jump_pos", "input_dir", "throttle", "sounds"]
N, NE, E, SE, S, SW, W, NW, NONE = range(9)


def build() -> pathlib.Path:
    srcs = [ROOT / "tools" / "route_sim.c", ROOT / "port/platform/input_map.c",
            ROOT / "port/tests/bridge/dgroup_map.c", *sorted((ROOT / "port/game").glob("*.[ch]")),
            *sorted((ROOT / "port/tests/bridge").glob("*.h"))]
    import hashlib
    h = hashlib.sha1(b"".join(s.read_bytes() for s in srcs)).hexdigest()[:12]
    exe = SIM_EXE.with_name(f"route_sim_{h}.exe")     # per source version: a running
    if exe.exists():                                   # search keeps its own binary
        return exe
    env = dict(os.environ, PATH=MINGW + os.pathsep + os.environ["PATH"])
    subprocess.run(["gcc", "-O2", "-std=c11", "-I", str(ROOT / "port/game"), "-I",
                    str(ROOT / "port/platform"), "-I", str(ROOT / "port/tests/bridge"),
                    *[str(s) for s in srcs if s.suffix == ".c"], "-o", str(exe)],
                   check=True, env=env)
    return exe


def resources() -> tuple:
    """levels.bin (g_levels as DAVE.EXE initialises it) and demos.bin, as
    tools/native_check.py writes them for the bridge."""
    import far_data
    import levels
    work = ROOT / "build" / "route"
    work.mkdir(parents=True, exist_ok=True)
    exe = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
    demos_at = far_data.segment(exe, "demos")["start"]
    (work / "demos.bin").write_bytes(exe[demos_at:demos_at + 4368 + 0x3000])
    _, base, _ = levels.find_levels_base(exe)
    (work / "levels.bin").write_bytes(exe[base:base + levels.NUM_LEVELS * levels.RECORD_SIZE])
    return work / "levels.bin", work / "demos.bin"


def snapshot(run: pathlib.Path, tick: int) -> bytes:
    L = oracle.DGROUP_LIVE_LEN
    with open(run / "ticks.bin", "rb") as f:
        f.seek((tick - 1) * L)
        return f.read(L)


def _parse(line: str) -> dict:
    vals = line.split()
    d = {k: int(v) for k, v in zip(FIELDS[:-1], vals[:-1])}
    d["sounds"] = [] if vals[-1] == "-" else [int(s) for s in vals[-1].split(",")]
    return d


class Sim:
    """One simulator process, started at the head of `tick` of `run`."""

    def __init__(self, run: pathlib.Path, tick: int, snap: bytes | None = None):
        exe = build()
        lv, dm = resources()
        path = ROOT / "build" / "route" / f"snap_{os.getpid()}_{id(self)}.bin"
        path.write_bytes(snap if snap is not None else snapshot(run, tick))
        self.p = subprocess.Popen([str(exe), str(path), str(lv), str(dm)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1 << 16)

    def cmd(self, text: str):
        self.p.stdin.write(text + "\n")

    def run(self, inputs) -> list:
        """Steps a list of (dir, fire, jump); one pipe round trip."""
        inputs = list(inputs)
        out = []
        for at in range(0, len(inputs), 256):     # bounded: neither pipe can fill up
            part = inputs[at:at + 256]
            self.p.stdin.write("".join(f"s {d} {f} {j}\n" for d, f, j in part) + "f\n")
            self.p.stdin.flush()
            out += [_parse(self.p.stdout.readline()) for _ in part]
        return out

    def step(self, dir: int = NONE, fire: int = 0, jump: int = 0) -> dict:
        return self.run([(dir, fire, jump)])[0]

    def save(self, slot: int):
        self.cmd(f"save {slot}")

    def load(self, slot: int):
        self.cmd(f"load {slot}")

    def free(self, slot: int):
        self.cmd(f"free {slot}")

    def close(self):
        try:
            self.p.stdin.write("q\n")
            self.p.stdin.flush()
        except OSError:
            pass
        self.p.wait()


def input_of(keys_down, scans=DEFAULT_SCANS) -> tuple:
    """(dir, fire, jump) the keyboard reader derives from a key_down set."""
    down = set(keys_down)
    dx = dy = 0
    k = [s in down for s in scans]
    if k[0]: dy = -1
    if k[2]: dx = 1
    if k[4]: dy = 1
    if k[6]: dx = -1
    if k[1]: dy, dx = -1, 1
    if k[7]: dy, dx = -1, -1
    if k[3]: dy, dx = 1, 1
    if k[5]: dy, dx = 1, -1
    dir_of = [7, 0, 1, 6, 8, 2, 5, 4, 3]
    return dir_of[(dy + 1) * 3 + dx + 1], int(k[8]), int(k[9])


def replay_check(run: pathlib.Path, start: int = 2, end: int | None = None):
    """Simulate run's ticks start.. with their recorded key tables; compare with
    the next tick head. Returns (ticks that agree, first mismatch or None)."""
    ticks = [json.loads(l) for l in (run / "ticks.jsonl").read_text().splitlines()]
    end = min(end or len(ticks), len(ticks))
    sim = Sim(run, start)
    res = sim.run(input_of(ticks[t - 1]["keys_down"]) for t in range(start, end))
    sim.close()
    for k, (t, r) in enumerate(zip(range(start, end), res)):
        nxt = ticks[t]          # head of tick t+1
        want = {"x": nxt["player_x"], "y": nxt["player_y"], "state": nxt["dave_state"],
                "level": nxt["level"], "scroll": nxt["view_column"], "score": nxt["score"],
                "lives": nxt["lives"], "retraces": nxt["frames_since_prev"]}
        got = {k2: r[k2] for k2 in want}
        if got != want:
            return k, {"tick": t, "sim": got, "oracle": want}
    return end - start, None


def plan_check(run: pathlib.Path, start: int, results: list):
    """Did the original follow a plan? Compares the plan's per-tick results
    with the run's next tick heads; returns the first differing tick or None."""
    ticks = [json.loads(l) for l in (run / "ticks.jsonl").read_text().splitlines()]
    for k, r in enumerate(results):
        if start + k >= len(ticks):
            return None
        t = ticks[start + k]
        if (t["player_x"], t["player_y"], t["dave_state"], t["level"], t["view_column"], t["score"]) != \
                (r["x"], r["y"], r["state"], r["level"], r["scroll"], r["score"]):
            return start + k, {"oracle": (t["player_x"], t["player_y"], t["dave_state"], t["level"],
                                          t["view_column"], t["score"]),
                               "plan": (r["x"], r["y"], r["state"], r["level"], r["scroll"], r["score"])}
    return None


def start_input(run: pathlib.Path, tick: int) -> tuple:
    """The input process_input read at `tick` in `run` (keys_at_read.jsonl when
    captured, else the tick head's key table): a plan starting at that tick
    must begin with it, since a key held into the tick cannot be released
    before its read."""
    path = run / "keys_at_read.jsonl"
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["tick"] == tick:
                return input_of(r["keys_down"])
    t = json.loads((run / "ticks.jsonl").read_text().splitlines()[tick - 1])
    return input_of(t["keys_down"])


def demo_inputs(index: int) -> list:
    """The per-tick (dir, fire, jump) a built-in demo feeds process_input,
    until its 0x30 end byte: ' ' n = the tick itself with the live (idle)
    input, then n idle ticks; else dir = low nibble, fire = bit 7, jump =
    (signed byte) >> 6 (== 1 only for bit pattern 01xxxxxx)."""
    import struct
    import demos
    import far_data
    blob = far_data.segment_bytes(far_data.DEFAULT_EXE.read_bytes(), demos.SEGMENT)
    pos = struct.unpack_from("<I", blob, 4 + 4 * index)[0] + 1      # after the level byte
    out, repeat = [], 0
    while True:
        if repeat:
            repeat -= 1
            out.append((NONE, 0, 0))
            continue
        b = blob[pos]
        if b == 0x20:
            repeat = blob[pos + 1]
            pos += 2
            out.append((NONE, 0, 0))
        elif b == 0x30:
            return out
        else:
            sb = b - 256 if b & 0x80 else b
            out.append((b & 0xF, (b >> 7) & 1, int((sb >> 6) == 1)))
            pos += 1


# ------------------------------------------------------------------ search

def alive(r) -> bool:
    return bool(r["state"] & 0x20) and not r["state"] & 0x40 and r["lives"] >= 0


def decision(r) -> bool:
    """A state where a new macro starts: standing/walking, climbing at rest,
    or flying with the jetpack."""
    s = r["state"]
    return s in (0x24, 0x22, 0x21) or s == 0x26


def macros(r, jetpack=False, fine=False):
    """Candidate input sequences from a decision state."""
    out = []
    walks = (1, 3, 6, 9, 12, 18, 24, 36, 48, 72, 96) if fine else (3, 6, 12, 24, 48, 96)
    s = r["state"]
    if s & 0x01:          # jetpack flight: 8 directions, n ticks
        for d in range(8):
            for n in (2, 4, 8, 16, 32):
                out.append([(d, 0, 0)] * n)
        if r.get("gun"):
            for d in (E, W):
                out.append([(d, 0, 0), (NONE, 1, 0), (NONE, 1, 0), (NONE, 0, 0)])
        out.append([(NONE, 0, 1), (NONE, 0, 0)])    # toggle off (Alt tap): Dave falls
        return out
    if s & 0x02:          # climbing
        for d in (N, S, E, W, NE, NW):
            for n in (2, 4, 8, 16, 32):
                out.append([(d, 0, 0)] * n)
        return out
    for d in (E, W):
        for n in walks:
            out.append([(d, 0, 0)] * n)
    holds = (0, 4, 8, 16, 24, 32, 48, 64, 96)
    for d0, air in ((NE, E), (NW, W), (N, E), (N, W)):
        for m in holds:
            out.append([(d0, 0, 0)] * 3 + [(air, 0, 0)] * m)
    out.append([(N, 0, 0)] * 3)
    for d in (S, N):      # onto a ladder/tree
        out.append([(d, 0, 0)] * 4)
    if jetpack and r["jetpack"]:
        out.append([(NONE, 0, 1), (NONE, 0, 0)])    # toggle on: Alt tap (release triggers)
    if r.get("gun"):          # face left / right, then a Ctrl tap (the release fires)
        for d in (E, W):
            out.append([(d, 0, 0), (NONE, 1, 0), (NONE, 1, 0), (NONE, 0, 0)])
        for d in (E, W):      # fire while walking
            out.append([(d, 1, 0)] * 2 + [(d, 0, 0)] * 10)
    return out


class Node:
    __slots__ = ("slot", "cost", "parent", "inputs", "r", "polls")

    def __init__(self, slot, cost, parent, inputs, r, polls):
        self.slot, self.cost, self.parent, self.inputs, self.r, self.polls = \
            slot, cost, parent, inputs, r, polls

    def path(self):
        seq, polls, n = [], [], self
        chain = []
        while n is not None:
            chain.append(n)
            n = n.parent
        for n in reversed(chain):
            base = len(seq)
            seq += n.inputs
            polls += [(base + k, p) for k, p in n.polls]
        return seq, polls


def search(sim: Sim, goal, key=None, max_nodes=4000, settle_max=200, jetpack=False, fine=False,
           allow=None, log=False, wait_dir=E, time_bucket=0, heuristic=None):
    """Best-first search for the fewest ticks from the sim's current state to a
    result `goal(r)` holds for. `key(r)` dedups decision states; `allow(r)`
    prunes. Returns (inputs, per-tick results, [(index, first_poll)])."""
    key = key or (lambda r: (r["level"], r["warp"], r["scroll"] * 16 + r["x"], r["y"], r["state"],
                             r["trophy"], r["jetpack"], r["gun"], r["input_dir"]))
    sim.cmd(f"w {wait_dir}")
    sim.save(0)
    root_r = {"state": 0x24, "jetpack": 1}     # the root expands as a standing state
    root = Node(0, 0, None, [], None, [])
    heap = [(0, 0, root)]
    seen = set()
    stats = {}
    next_slot, counter, expanded = 1, 1, 0
    while heap and expanded < max_nodes:
        cost, _, node = heapq.heappop(heap)
        expanded += 1
        cands = macros(node.r or root_r, jetpack, fine)
        if node.r and not decision(node.r):
            cands = [[]]
        for mac in cands:
            sim.load(node.slot)
            seq = mac + [(NONE, 0, 0)] * settle_max
            res = sim.run(seq)
            cut, hit, ok = None, False, True
            for i, r in enumerate(res):
                if not alive(r) or (allow and not allow(r)):
                    ok = False
                    break
                if goal(r):
                    cut, hit = i + 1, True
                    break
                if i >= len(mac) and decision(r) and i > 0:
                    cut = i + 1
                    break
            if not ok or cut is None:
                stats["dead" if not ok else "unsettled"] = stats.get("dead" if not ok else "unsettled", 0) + 1
                if not ok and log == 2:
                    print("   died", r["scroll"] * 16 + r["x"], r["y"], hex(r["state"]), i, mac[:1], len(mac))
                continue
            k = key(res[cut - 1])
            if time_bucket:      # revisit a place later: monsters and shots move on
                k = (k, (node.cost + cut) // time_bucket)
            if k in seen and not hit:
                continue
            seen.add(k)
            polls = [(i, res[i]["first_poll"]) for i in range(cut) if res[i]["first_poll"] >= 0]
            sim.load(node.slot)
            sim.run(seq[:cut])
            child = Node(next_slot, node.cost + cut, node, seq[:cut], res[cut - 1], polls)
            sim.save(next_slot)
            next_slot += 1
            if hit:
                seqs, polls = child.path()
                sim.load(0)
                full = sim.run(seqs)
                if log:
                    print(f"goal after {expanded} expansions, {len(seqs)} ticks")
                return seqs, full, polls
            heapq.heappush(heap, (child.cost + (heuristic(child.r) if heuristic else 0), counter, child))
            counter += 1
        if log and expanded % 100 == 0:
            r = node.r or {}
            print(f"  {expanded} expanded, {len(heap)} open, cost {cost}, at "
                  f"{r.get('scroll', 0) * 16 + r.get('x', 0)},{r.get('y')} score {r.get('score')}")
    if log:
        print(f"search failed after {expanded} expansions: {stats}, {len(seen)} states")
    return None


# ------------------------------------------------------------------ events

def plan_events(heads0: float, period: float, inputs: list, results: list, held_before=(),
                wait_dir=E) -> tuple:
    """Key events for per-tick `inputs` whose first tick head is at heads0 ms.
    Each tick's keys change half a retrace before its head; a tick whose
    waiting loop polled with the wait direction (first_poll >= 0) gets that
    key pressed half a retrace before the poll (it then stays held into the
    next tick, whose planned input must include it). Returns (events, heads)."""
    heads = [heads0]
    for r in results:
        heads.append(heads[-1] + r["retraces"] * period)
    ev, held = [], set(held_before)
    forced_prev = False
    for k, (d, f, j) in enumerate(inputs):
        if d == NONE and forced_prev:      # route_sim.c holds the waited-for key one more tick
            d = wait_dir
        forced_prev = False
        want = set()
        if d in DIR_KEYS:
            want.add(DIR_KEYS[d])
        if f:
            want.add(FIRE_KEY)
        if j:
            want.add(JUMP_KEY)
        if want != held:
            ms = int(round(heads[k] - period / 2))
            for key in sorted(held - want):
                ev.append((ms, "keyup", key))
            for key in sorted(want - held):
                ev.append((ms, "keydown", key))
            held = want
        fp = results[k]["first_poll"]
        if fp >= 0 and d == NONE:
            ms = int(round(heads[k] + (fp - 0.5) * period))
            ev.append((ms, "keydown", DIR_KEYS[wait_dir]))
            held = {DIR_KEYS[wait_dir]}
            forced_prev = True
    return ev, heads


def parse_moves(text: str) -> list:
    """'2x30 8x5 1/j' style: dir x count, optional /f (fire) /j (jump)."""
    out = []
    for tok in text.split():
        mods = tok.split("/")
        d, _, n = mods[0].partition("x")
        n = int(n or 1)
        out += [(int(d), int("f" in mods[1:]), int("j" in mods[1:]))] * n
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("run", type=pathlib.Path)
    c.add_argument("--from", dest="start", type=int, default=2)
    c.add_argument("--to", dest="end", type=int, default=None)
    s = sub.add_parser("sim")
    s.add_argument("run", type=pathlib.Path)
    s.add_argument("tick", type=int)
    s.add_argument("moves")
    args = ap.parse_args()
    if args.cmd == "check":
        n, bad = replay_check(args.run, args.start, args.end)
        print(f"{n} ticks agree" + (f"; first mismatch {bad}" if bad else ""))
    else:
        sim = Sim(args.run, args.tick)
        for k, r in enumerate(sim.run(parse_moves(args.moves))):
            print(args.tick + k, r)
        sim.close()


if __name__ == "__main__":
    main()
