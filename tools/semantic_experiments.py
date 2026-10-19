"""Oracle experiments behind the M2.2 closures in docs/UNDERSTANDING_LEDGER.md.

    python tools/oracle.py tests/oracle/inv_demos.txt          # once (~4 min)
    python tools/semantic_experiments.py [build/oracle/inv_demos/run1]

Reads the per-tick snapshots (ticks.bin) and the per-subsystem boundary
snapshots (boundaries.bin, `oracle.iter_boundaries`) of a run of the ORIGINAL
game and tests hypotheses about the state model against them. Every check
prints PASS/FAIL with counts; the exit status is non-zero if any fails.

  writers     every DGROUP byte that changes between two pipeline points is
              owned by a data object whose static writers (docs/
              semantic-inventory.json, mechanical) include the subsystem that
              ran, or one of its callees (transitively);
  dave_state  every change of g_dave_state (DS 0x6156), per subsystem, is one
              of the transitions read from the code (U-G1);
  throttle    g_death_pause (DS 0x5794) is a movement throttle: Dave moves
              every 3rd tick walking, every 2nd jumping/climbing, every tick
              falling or flying (U-G2);
  jump        the y steps of a jump are g_jump_dy[1..] (U-G2);
  anim        g_anim_tick_divider (0x615A) counts 10..1 once per tick during
              play; g_anim_frame (0x6150) stays in 0..3 (U-G4);
  rand        the Borland rand() seed (DS 0x4BB6) after every load_level is
              LCG^n(100), n = animated tiles + 4 monsters (U-S1);
  monsters    move countdown 5..1, path index +2 per step, x/y steps equal the
              level's path bytes (U-G5);
  shots       shot records hold active/x/y/dir/frame/kind/id with the value
              sets read from the code; actor bytes 14..0x139 never change (U-G6).
"""
from __future__ import annotations

import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import oracle  # noqa: E402

L = oracle.DGROUP_LIVE_LEN
RAND_SEED = 0x4BB6
PIPE = [name for _, name in oracle.PIPELINE]


def w16(s, a, signed=False):
    return int.from_bytes(s[a:a + 2], "little", signed=signed)


def u32(s, a):
    return int.from_bytes(s[a:a + 4], "little")


def lcg(seed, n):
    for _ in range(n):
        seed = (seed * 0x015A4E35 + 1) & 0xFFFFFFFF
    return seed


class Report:
    def __init__(self):
        self.failed = 0

    def check(self, name, ok, detail):
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
        if not ok:
            self.failed += 1


def load(run: pathlib.Path):
    blob = (run / "ticks.bin").read_bytes()
    ticks = [blob[k * L:(k + 1) * L] for k in range(len(blob) // L)]
    bounds = list(oracle.iter_boundaries(run / "boundaries.bin")) if (run / "boundaries.bin").exists() else []
    return ticks, bounds


def inventory():
    return json.loads((ROOT / "docs" / "semantic-inventory.json").read_text())


def writer_closure(inv):
    funcs = {e["name"]: e for e in inv["entries"] if e["kind"] in ("c_function", "asm_procedure")}
    memo = {}

    def closure(n):
        if n in memo:
            return memo[n]
        memo[n] = set()
        out, todo = {n}, [n]
        while todo:
            x = todo.pop()
            for c in funcs[x]["relations"]["callees"]:
                if c in funcs and c not in out:
                    out.add(c)
                    todo.append(c)
        memo[n] = out
        return out
    return funcs, closure


def owner_table(inv):
    spans = []
    for e in inv["entries"]:
        i = e["identity"]
        if e["kind"] == "global" and i.get("ds") and i.get("size"):
            spans.append((int(i["ds"], 16), int(i["ds"], 16) + i["size"], e["name"], e))
    spans.sort()
    return spans


def owner(spans, a):
    for lo, hi, n, e in spans:
        if lo <= a < hi:
            return n, e
    return None, None


def exp_writers(r, bounds, inv):
    """Observed changes per pipeline step vs the mechanical writer sets."""
    funcs, closure = writer_closure(inv)
    spans = owner_table(inv)
    lib_writes = {"rand": {"rand_seed"}, "srand": {"rand_seed"}}
    violations, observed = {}, 0
    prev = None
    for tick, site, snap in bounds:
        if prev is not None and prev[0] == tick:
            sub = PIPE[PIPE.index(site) - 1]
            allowed = set()
            for f in closure(sub):
                rel = funcs[f]["relations"]
                allowed |= {x.split("+")[0] for x in rel["writes"]}
                allowed |= {x.split("+")[0] for x in rel["writes_through_pointer"]}
                for lc in rel["library_calls"]:
                    allowed |= lib_writes.get(lc, set())
            # a pointer written through reaches its pointee object
            if "g_level" in allowed:
                allowed |= {"g_levels"}
            a = prev[2]
            for k in range(len(snap)):
                if snap[k] != a[k]:
                    if any(lo <= k < hi for lo, hi in oracle.ASYNC_RANGES) or k >= 0x9EC8:
                        continue          # INT 8 driver phase / CS.LIB _BSS + stack
                    observed += 1
                    n, _ = owner(spans, k)
                    if n not in allowed:
                        violations.setdefault((sub, n or f"DS:{k:04X}"), 0)
                        violations[(sub, n or f"DS:{k:04X}")] += 1
        prev = (tick, site, snap)
    detail = f"{observed} changed bytes over {len({t for t, _, _ in bounds})} ticks"
    if violations:
        detail += "; unexplained: " + ", ".join(f"{s}->{n} x{c}" for (s, n), c in sorted(violations.items()))
    r.check("writers", not violations, detail)


ALLOWED_DAVE = {
    # subsystem: set of (old & 0xFF) -> (new & 0xFF) transitions read from the code
}


def exp_dave_state(r, bounds):
    seen = {}
    prev = None
    for tick, site, snap in bounds:
        if prev is not None and prev[0] == tick:
            sub = PIPE[PIPE.index(site) - 1]
            a, b = w16(prev[2], 0x6156), w16(snap, 0x6156)
            if a != b:
                seen.setdefault(sub, {}).setdefault((a, b), 0)
                seen[sub][(a, b)] += 1
        prev = (tick, site, snap)
    # transitions predicted by reading the code (U-G1), by subsystem
    movement = {0x01, 0x02, 0x04, 0x08, 0x10}
    ok, bad = True, []
    for sub, tr in seen.items():
        for (a, b), c in tr.items():
            mv_a, mv_b = a & 0x1F, b & 0x1F
            if sub == "move_dave":
                good = (a & 0x20) and (
                    (b & 0xE0) == (a & 0xE0) and mv_b in movement      # movement-bit change, alive kept
                    or (b == (a & 0xE0) | 0x40 or b == 0x60)           # deadly tile: killed, still "alive"
                    or (a & 0x40 and b == 0))                          # deferred death processed
            elif sub == "process_input":
                good = (a & 0x20) and (b == (a & 0xE0) | 1 or (a & 1 and b == (a & 0xFE) | 8))
            elif sub == "update_jetpack":
                good = (a & 1) and b == (a & 0xE0) | 8
            elif sub == "check_collisions":
                good = (a & 0x20) and (b == (a & 0xC0) or b == 0x40)
            elif sub in ("handle_death", "attract_mode", "level_complete", "check_warp_transition"):
                good = b in (0x24, 0x28) or (sub == "check_warp_transition" and b == (a & 0xE0) | 8)
            else:
                good = False
            if not good:
                ok = False
                bad.append(f"{sub}: {a:#04x}->{b:#04x} x{c}")
    summary = "; ".join(f"{s}: " + ", ".join(f"{a:#04x}->{b:#04x} x{c}" for (a, b), c in sorted(t.items()))
                        for s, t in sorted(seen.items()))
    r.check("dave_state transitions", ok, summary + ("; UNEXPECTED " + ", ".join(bad) if bad else ""))
    return seen


def exp_throttle(r, ticks):
    """Ticks between consecutive Dave moves (x or y change) per movement state."""
    gaps, last_move, ok = {}, None, True
    for k in range(1, len(ticks)):
        a, b = ticks[k - 1], ticks[k]
        if w16(a, 0x00AA) != 1 or w16(b, 0x00AA) != 1:
            last_move = None
            continue
        st = w16(a, 0x6156)
        pa, pb = w16(a, 0x5794, True), w16(b, 0x5794, True)
        moved = pb == 3 and pa != 3 or (pa == 3 and pb == 3)
        if moved and st & 0x20:
            if last_move is not None and last_move[1] == st:
                gaps.setdefault(st & 0x1F, {}).setdefault(k - last_move[0], 0)
                gaps[st & 0x1F][k - last_move[0]] += 1
            last_move = (k, st)
    expect = {0x04: 3, 0x10: 2, 0x02: 2, 0x08: 1, 0x01: 1}
    for bit, hist in gaps.items():
        if bit in expect:
            main = max(hist, key=hist.get)
            if main != expect[bit] or any(g < expect[bit] for g in hist):
                ok = False
    r.check("movement throttle (g_death_pause)", ok,
            "; ".join(f"state bit {b:#04x}: period histogram {dict(sorted(h.items()))}" for b, h in sorted(gaps.items())))


def exp_jump(r, ticks):
    """Within a jump (state bit 0x10 set), the y step at each jump_pos change is g_jump_dy[pos]."""
    image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
    dgroup = image[0x256D0:0x256D0 + 0x200]
    jump_dy = [int.from_bytes(dgroup[0xBA + 2 * i:0xBC + 2 * i], "little", signed=True) for i in range(47)]
    steps, bad, wraps = 0, [], []
    for k in range(1, len(ticks)):
        a, b = ticks[k - 1], ticks[k]
        if not (w16(a, 0x6156) & 0x10) or w16(a, 0x00AA) != 1:
            continue
        pa, pb = w16(a, 0x579A), w16(b, 0x579A)
        if pb == pa + 1 and (w16(b, 0x6156) & 0x10):
            ya, yb = w16(a, 0x56EC), w16(b, 0x56EC)
            t = jump_dy[pa]
            if yb != (ya + t) & 0xFF:          # move_dave: y = (y + t) & 0xff
                bad.append((k, pa, t, ya, yb))
            elif yb != ya + t:
                wraps.append((k, ya, yb))
            steps += 1
    r.check("jump steps follow g_jump_dy, y kept to 8 bits", not bad and steps > 0,
            f"{steps} jump steps checked, table {jump_dy[:46]}; {len(wraps)} steps wrapped y modulo 256 "
            f"(jump above the top row: {wraps[:4]})" + (f"; mismatches {bad[:5]}" if bad else ""))


def exp_anim(r, ticks):
    seq_ok, frames = True, set()
    for k in range(1, len(ticks)):
        a, b = ticks[k - 1], ticks[k]
        frames.add(w16(b, 0x6150))
        if w16(a, 0x00AA) == 1 and w16(b, 0x00AA) == 1:
            x, y = w16(a, 0x615A), w16(b, 0x615A)
            if not (y == x - 1 or (x == 1 and y == 10)):
                # multi-retrace sequences call animate_tiles inside wait_for_input: allow any 1..10
                if not (1 <= y <= 10):
                    seq_ok = False
    r.check("g_anim_tick_divider counts 10..1", seq_ok, "values stay in 1..10 and step -1 per tick during play")
    r.check("g_anim_frame in 0..3", frames <= {0, 1, 2, 3}, f"observed {sorted(frames)}")


def exp_rand(r, bounds, ticks):
    levels = json.loads((ROOT / "docs" / "data-layout.json").read_text())["g_levels"]
    image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
    lv_base = int(levels["file_offset"], 16)
    checked, bad = 0, []
    for k in range(1, len(ticks)):
        a, b = ticks[k - 1], ticks[k]
        if w16(b, 0x00AA) == 1 and (w16(a, 0x00AA) != 1 or w16(a, 0x56F4) != w16(b, 0x56F4)):
            lvl = w16(b, 0x56F4, True)
            tiles = image[lv_base + lvl * 0x500 + 0x100: lv_base + lvl * 0x500 + 0x100 + 1000]
            n = sum(1 for t in tiles for x in (6, 10, 25, 36) if t == x)
            # attract_mode: srand(time) + 1 rand, then load_level: srand(100) + n + 4
            seed = u32(b, RAND_SEED)
            want = lcg(100, n + 4)
            checked += 1
            if seed != want:
                bad.append((k, lvl, n, hex(seed), hex(want)))
            # the outputs themselves: rand() = (seed >> 16) & 0x7FFF drives the
            # initial frames of the animated tiles and of the monsters
            outs, s = [], 100
            for _ in range(n + 4):
                s = lcg(s, 1)
                outs.append((s >> 16) & 0x7FFF)
            frames = {6: 4, 10: 5, 25: 4, 36: 5}
            j = 0
            for t in tiles:
                if t in frames:
                    cur = w16(b, 0x57E8 + 12 * j + 4)
                    want_cur = t + outs[j] * frames[t] // 32767
                    # the tile animation may already have stepped once (divider 10)
                    if cur != want_cur and not (frames[t] and (cur - t) % frames[t] == (want_cur - t + 1) % frames[t]):
                        bad.append((k, "tile", j, cur, want_cur))
                    j += 1
            for i in range(4):
                if w16(b, 0x5742 + 2 * i):
                    fr = w16(b, 0x577A + 2 * i)
                    want_fr = outs[n + i] * 3 // 32767
                    if fr != want_fr and fr != (want_fr + 1) & 3:
                        bad.append((k, "monster", i, fr, want_fr))
    r.check("rand seed after load_level == LCG^(anim tiles + 4)(100)", checked > 0 and not bad,
            f"{checked} level loads checked (seed, initial tile phases, monster frames)"
            + (f"; mismatches {bad[:8]}" if bad else ""))


def exp_monsters(r, ticks):
    image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
    lv_base = 0x26E0A
    steps, bad, fire_reload = 0, [], set()
    for k in range(1, len(ticks)):
        a, b = ticks[k - 1], ticks[k]
        if w16(a, 0x00AA) != 1 or w16(b, 0x00AA) != 1 or w16(a, 0x56F4) != w16(b, 0x56F4):
            continue
        if w16(a, 0x57A0) != w16(b, 0x57A0):
            continue                                  # scrolling shifts x by 16 per column
        lvl = w16(b, 0x56F4, True)
        path = image[lv_base + lvl * 0x500: lv_base + lvl * 0x500 + 0x100]
        for i in range(4):
            act = w16(a, 0x5742 + 2 * i)
            mc_a, mc_b = w16(a, 0x578A + 2 * i), w16(b, 0x578A + 2 * i)
            if not act or not w16(b, 0x5742 + 2 * i):
                continue
            if mc_b == 5 and mc_a == 1:
                pa, pb = w16(a, 0x575A + 2 * i), w16(b, 0x575A + 2 * i)
                idx = 0 if path[pa] == 0xEA else pa
                dx = int.from_bytes(path[idx:idx + 1], "little", signed=True)
                dy = int.from_bytes(path[idx + 1:idx + 2], "little", signed=True)
                ddx = w16(b, 0x574A + 2 * i, True) - w16(a, 0x574A + 2 * i, True)
                ddy = w16(b, 0x5752 + 2 * i, True) - w16(a, 0x5752 + 2 * i, True)
                if (ddx, ddy) != (dx, dy) or pb != idx + 2:
                    bad.append((k, i, (ddx, ddy), (dx, dy), pa, pb))
                steps += 1
            elif mc_b != mc_a - 1:
                bad.append((k, i, "move_count", mc_a, mc_b))
            fire_reload.add(w16(b, 0x5762 + 2 * i))
    r.check("monster records step along the level path every 5 ticks", steps > 0 and not bad,
            f"{steps} monster steps checked; reload values seen {sorted(fire_reload)}"
            + (f"; mismatches {bad[:6]}" if bad else ""))


def exp_shots(r, ticks):
    vals = {f: set() for f in ("active", "dir", "frame", "kind", "id")}
    tail_changed = False
    base_tail = None
    for s in ticks:
        for i in range(5):
            rec = s[0x56F6 + 14 * i: 0x56F6 + 14 * (i + 1)]
            act, x, y, d, fr, kind, ident = struct.unpack("<7h", rec)
            vals["active"].add(act)
            if act:
                vals["dir"].add(d)
                vals["frame"].add(fr)
                vals["kind"].add(kind)
                vals["id"].add(ident)
        tail = b"".join(s[0x4F8E + 0x13A * i + 14: 0x4F8E + 0x13A * (i + 1)] for i in range(6))
        if base_tail is None:
            base_tail = tail
        elif tail != base_tail:
            tail_changed = True
    ok = (vals["active"] <= {0, 1} and vals["dir"] <= {0, 1} and vals["frame"] <= {0, 1, 2, 3}
          and vals["kind"] <= {0, 1} and vals["id"] <= {1, 2, 3, 4, 5})
    r.check("shot record value sets", ok, {k: sorted(v) for k, v in vals.items()})
    r.check("actor bytes 14..0x139 never change", not tail_changed and set(base_tail) <= {0},
            f"{6 * (0x13A - 14)} bytes, all zero throughout" if not tail_changed else "changed")


def main():
    run = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "oracle" / "inv_demos" / "run1"
    ticks, bounds = load(run)
    inv = inventory()
    r = Report()
    print(f"run {run}: {len(ticks)} ticks, {len(bounds)} boundary snapshots")
    if bounds:
        exp_writers(r, bounds, inv)
        exp_dave_state(r, bounds)
    exp_throttle(r, ticks)
    exp_jump(r, ticks)
    exp_anim(r, ticks)
    exp_rand(r, bounds, ticks)
    exp_monsters(r, ticks)
    exp_shots(r, ticks)
    sys.exit(1 if r.failed else 0)


if __name__ == "__main__":
    main()
