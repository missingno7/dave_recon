"""Control-flow-graph census of the game's code in build/DAVE_unpacked.exe.

Replaces the linear "walk to the first RET" scan with recursive traversal:

* Entry points: _main, every direct near-CALL target, every coverage gap
  that begins with a recognised prologue (functions reached only through
  pointers: interrupt handlers, callbacks), and explicit manual seeds.
* Each function is traversed instruction by instruction following every
  conditional/unconditional branch; RET/RETF/IRET and indirect JMPs end a
  path. A switch is recognised by Turbo C's fixed idiom
      cmp bx,N ; ja L ; shl bx,1 ; jmp word ptr cs:[bx+TABLE]
  (TABLE's N+1 entries become successors, and TABLE's bytes are recorded as
  in-function data, not code).
* A function's extent is [entry, end) where end is the maximum byte reached
  by its code or its jump tables. Turbo C emits functions contiguously, so
  every byte of the game-code range must be covered exactly once; any gap is
  reported (unreached code or embedded data), never silently absorbed.

All addresses are CS offsets (= file offset - 0x200, CS base paragraph 0).
Output: docs/function-census.json (schema dave-function-census-v3).

Usage: python tools/cfg.py [--code-end 0x9413] [--write]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct

import capstone
from capstone import x86

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXE = ROOT / "build" / "DAVE_unpacked.exe"
OUT = ROOT / "docs" / "function-census.json"
HDR = 0x200
MAIN = 0x239

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
md.detail = True

COND_JUMPS = {
    "jo", "jno", "jb", "jae", "je", "jne", "jbe", "ja", "js", "jns", "jp", "jnp",
    "jl", "jge", "jle", "jg", "jcxz", "loop", "loope", "loopne",
}

PROLOGUES = (
    (b"\x55\x8b\xec", "c_prologue"),                                  # push bp; mov bp,sp
    (b"\x50\x53\x51\x52\x06\x1e\x56\x57\x55", "interrupt_prologue"),  # TC `interrupt`
)


class Image:
    def __init__(self, data: bytes):
        self.data = data
        self.lm = data[HDR:]

    def insn(self, cs_off: int):
        for i in md.disasm(self.lm[cs_off:cs_off + 16], cs_off, 1):
            return i
        return None

    def word(self, cs_off: int) -> int:
        return struct.unpack_from("<H", self.lm, cs_off)[0]


def reloc_sites(img: Image):
    h = struct.unpack_from("<14H", img.data, 0)
    return [struct.unpack_from("<HH", img.data, h[12] + 4 * i) for i in range(h[3])]


def walk_function(img: Image, entry: int, code_end: int):
    """Return (insns{addr: insn}, tables[(addr, count, targets)], calls, notes)."""
    insns = {}
    tables = []
    calls = []
    indirect = []
    work = [entry]
    while work:
        pc = work.pop()
        while pc not in insns:
            if not (0 <= pc < code_end):
                indirect.append({"kind": "branch_outside_code", "target": pc})
                break
            i = img.insn(pc)
            if i is None:
                indirect.append({"kind": "undecodable", "at": pc})
                break
            insns[pc] = i
            nxt = pc + i.size
            m = i.mnemonic
            if m in ("ret", "retf", "iret"):
                break
            if m == "call":
                op = i.operands[0]
                if op.type == x86.X86_OP_IMM:
                    calls.append((pc, op.imm & 0xFFFF))
                else:
                    indirect.append({"kind": "indirect_call", "at": pc, "op": i.op_str})
                pc = nxt
                continue
            if m == "jmp":
                op = i.operands[0]
                if op.type == x86.X86_OP_IMM:
                    pc = op.imm & 0xFFFF
                    continue
                tbl = switch_table(img, insns, i)
                if tbl:
                    tables.append(tbl)
                    work.extend(tbl[2])
                else:
                    indirect.append({"kind": "indirect_jmp", "at": pc, "op": i.op_str})
                break
            if m in ("ljmp", "lcall"):
                indirect.append({"kind": m, "at": pc, "op": i.op_str})
                if m == "ljmp":
                    break
                pc = nxt
                continue
            if m in COND_JUMPS:
                work.append(i.operands[0].imm & 0xFFFF)
            pc = nxt
    return insns, tables, calls, indirect


def switch_table(img: Image, insns: dict, jmp):
    """Recognise `jmp word ptr cs:[bx+TABLE]` preceded by `cmp bx,N; ja`."""
    op = jmp.operands[0]
    if op.type != x86.X86_OP_MEM or op.mem.segment != x86.X86_REG_CS:
        return None
    if op.mem.base != x86.X86_REG_BX or op.mem.index != 0:
        return None
    table = op.mem.disp & 0xFFFF
    prev = sorted(a for a in insns if a < jmp.address)[-4:]
    count = None
    for a in reversed(prev):
        p = insns[a]
        if p.mnemonic == "cmp" and p.op_str.startswith("bx, "):
            count = p.operands[1].imm + 1
            break
    if count is None:
        return None
    targets = [img.word(table + 2 * k) for k in range(count)]
    return (table, count, targets)


def _end(f):
    ends = [a + i.size for a, i in f["insns"].items()]
    ends += [t + 2 * n for t, n, _ in f["tables"]]
    return max(ends)


def coverage_gaps(funcs, code_start, code_end):
    spans = sorted((e, _end(f)) for e, f in funcs.items())
    gaps, cursor = [], code_start
    for a, b in spans:
        if a > cursor:
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < code_end:
        gaps.append((cursor, code_end))
    return gaps


def _walk_pending(img, funcs, entries, pending, code_start, code_end):
    while pending:
        e = pending.pop()
        if e in funcs or not (code_start <= e < code_end):
            continue
        insns, tables, calls, indirect = walk_function(img, e, code_end)
        funcs[e] = {"insns": insns, "tables": tables, "calls": calls, "indirect": indirect}
        for _, tgt in calls:
            if tgt not in funcs:
                entries.setdefault(tgt, "call")
                pending.append(tgt)


def census(code_start: int, code_end: int, extra_seeds=()):
    """Walk from _main; then repeatedly seed any coverage gap that begins
    with a recognised prologue (functions reached only through pointers),
    plus explicitly supplied seeds (with evidence recorded by the caller)."""
    img = Image(EXE.read_bytes())
    entries = {MAIN: "main"}
    for s in extra_seeds:
        entries[s] = "manual_seed"
    funcs = {}
    pending = list(entries)
    while True:
        _walk_pending(img, funcs, entries, pending, code_start, code_end)
        new = []
        for a, b in coverage_gaps(funcs, code_start, code_end):
            for sig, why in PROLOGUES:
                if img.lm[a:a + len(sig)] == sig:
                    entries[a] = why
                    new.append(a)
        if not new:
            break
        pending = new
    result = [{"entry": e, "end": _end(f), "seed": entries.get(e, "call"), **f}
              for e, f in sorted(funcs.items())]
    return img, result, entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code-end", default="0x9413", help="CS offset where game code ends")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    code_end = int(args.code_end, 0)

    img, funcs, entries = census(MAIN, code_end)
    gaps, overlaps = [], []
    cursor = MAIN
    for f in funcs:
        if f["entry"] > cursor:
            gaps.append((cursor, f["entry"]))
        elif f["entry"] < cursor:
            overlaps.append((f["entry"], cursor))
        cursor = max(cursor, f["end"])
    if cursor < code_end:
        gaps.append((cursor, code_end))

    print(f"functions: {len(funcs)}")
    print(f"covered bytes: {sum(f['end'] - f['entry'] for f in funcs)} of {code_end - MAIN}")
    for a, b in gaps:
        print(f"GAP  cs {a:04x}-{b:04x} ({b - a} bytes) file {a + HDR:05x}")
    for a, b in overlaps:
        print(f"OVERLAP cs {a:04x}-{b:04x}")
    for f in funcs:
        for ind in f["indirect"]:
            print(f"INDIRECT in {f['entry']:04x}: {ind}")
        covered = set()
        for a, i in f["insns"].items():
            covered.update(range(a, a + i.size))
        for t, n, _ in f["tables"]:
            covered.update(range(t, t + 2 * n))
        holes = [a for a in range(f["entry"], f["end"]) if a not in covered]
        if holes:
            print(f"HOLES in {f['entry']:04x}: {len(holes)} bytes, first {holes[0]:04x}")

    def lang(f):
        head = img.lm[f["entry"]:f["entry"] + 24]
        if b"\x39\x26\x9a\x00" in head:            # -N stack check => compiled C
            return "C"
        if f["seed"] == "interrupt_prologue":
            return "C_interrupt"
        return "ASM"

    if args.write:
        out = {
            "schema": "dave-function-census-v3",
            "method": "recursive-traversal CFG from _main over direct near calls, plus "
                      "prologue-seeded coverage gaps; Turbo C switch jump tables resolved; "
                      "extent = max reached byte incl. tables",
            "address_convention": "cs = CS offset (file offset - 0x200); file = file offset",
            "code_range_cs": [MAIN, code_end],
            "functions": [
                {
                    "id": f"F_{f['entry'] + HDR:04X}",
                    "cs_start": f["entry"], "cs_end": f["end"],
                    "file_start": f["entry"] + HDR, "file_end": f["end"] + HDR,
                    "start": f["entry"] + HDR, "end": f["end"] + HDR,   # v2-compatible aliases (file offsets)
                    "size": f["end"] - f["entry"],
                    "seed": f["seed"],
                    "lang": lang(f),
                    "insn_count": len(f["insns"]),
                    "jump_tables": [{"cs": t, "entries": n, "targets": tg} for t, n, tg in f["tables"]],
                    "callees": sorted({c for _, c in f["calls"]}),
                    "call_sites": [{"cs": a, "target": c} for a, c in f["calls"]],
                    "unresolved_indirect": f["indirect"],
                }
                for f in funcs
            ],
            "gaps_cs": gaps,
            "overlaps_cs": overlaps,
        }
        OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        write_summary(out)


def write_summary(out):
    fs = out["functions"]
    by = {}
    for f in fs:
        by.setdefault(f["lang"], []).append(f)
    lines = [
        "# Function census (v3, generated by tools/cfg.py -- do not edit)", "",
        "Recursive-traversal CFG over the game code range "
        f"cs [{out['code_range_cs'][0]:#06x},{out['code_range_cs'][1]:#06x}) "
        "(file = cs + 0x200). Switch jump tables are resolved and owned by their "
        "function; extents end at the last byte reached (incl. tables and dead "
        "`jmp`s after `return`).", "",
        "| kind | functions | bytes |", "|---|---|---|",
    ]
    for k, v in sorted(by.items()):
        lines.append(f"| {k} | {len(v)} | {sum(f['size'] for f in v)} |")
    lines += ["", f"Gaps (bytes in the range owned by no function): "
              f"{sum(b - a for a, b in out['gaps_cs'])} bytes in {len(out['gaps_cs'])} spans:", ""]
    for a, b in out["gaps_cs"]:
        lines.append(f"- cs {a:#06x}-{b:#06x} ({b - a} bytes)")
    lines += ["", "Unresolved indirect control flow:", ""]
    for f in fs:
        for u in f["unresolved_indirect"]:
            lines.append(f"- {f['id']}: {u}")
    (ROOT / "docs" / "function-census.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
