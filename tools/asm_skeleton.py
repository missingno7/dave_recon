"""Draft TASM source for a CS range of build/DAVE_unpacked.exe (a starting point, not a verdict).

Linear-sweeps the range with capstone and prints TASM-syntax lines:
branch/call targets become labels (L_XXXX = CS offset), census function
starts become F_XXXX procs (census id = FILE offset), MZ relocation sites
become `DGROUP`, absolute DGROUP operands become V_XXXX (inside the module's
own data window, --data) or _D_XXXX externals, and cs: operands inside the
range become labels. Data ranges given with --dw/--db are emitted as tables.

The output is only a draft for a human to name, structure and simplify;
tools/match_asm.py is what decides whether a source is right.

Usage: python tools/asm_skeleton.py 0x73d6 0x7e59 [--dw 0x6f26:0x73d6] [--db a:b]
           [--data 0x132e:0x13a9]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys

import capstone
from capstone import x86

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from symbols import HDR  # noqa: E402

STRING_OPS = {"lodsb", "lodsw", "stosb", "stosw", "movsb", "movsw", "scasb", "scasw",
              "cmpsb", "cmpsw"}


def is_branch_insn(i) -> bool:
    return (i.group(capstone.CS_GRP_JUMP) or i.group(capstone.CS_GRP_CALL)
            or i.mnemonic.startswith(("j", "loop", "call")))


def hx(v: int) -> str:
    s = f"{v:X}h"
    return "0" + s if s[0] in "ABCDEF" else s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--dw", action="append", default=[])
    ap.add_argument("--db", action="append", default=[])
    ap.add_argument("--data", default=None, help="DGROUP window owned by this module a:b")
    ap.add_argument("--dscs", action="append", default=[],
                    help="code range a:b during which DS = CS (absolute operands are labels)")
    args = ap.parse_args()
    a, b = int(args.start, 0), int(args.end, 0)
    image = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()
    lm = image[HDR:]
    h = struct.unpack_from("<14H", image, 0)
    relocs = set()
    for i in range(h[3]):
        off, seg = struct.unpack_from("<HH", image, h[12] + 4 * i)
        relocs.add(seg * 16 + off)
    data_ranges = []
    for spec, kind in [(s, "dw") for s in args.dw] + [(s, "db") for s in args.db]:
        x, y = (int(v, 0) for v in spec.split(":"))
        data_ranges.append((x, y, kind))
    data_ranges.sort()
    dscs = [tuple(int(v, 0) for v in r.split(":")) for r in args.dscs]
    dwin = tuple(int(v, 0) for v in args.data.split(":")) if args.data else (0, 0)
    census = json.loads((ROOT / "docs" / "function-census.json").read_text())
    procs = {f["cs_start"]: f["id"] for f in census["functions"] if a <= f["cs_start"] < b}

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    md.detail = True

    def in_data(pc):
        return next((r for r in data_ranges if r[0] <= pc < r[1]), None)

    # pass 1: decode, collect targets
    insns = []
    pc = a
    targets = set()
    while pc < b:
        r = in_data(pc)
        if r:
            insns.append(("data", r))
            pc = r[1]
            continue
        i = next(md.disasm(lm[pc:pc + 16], pc, 1), None)
        if i is None:
            insns.append(("byte", pc))
            pc += 1
            continue
        insns.append(("insn", i))
        if is_branch_insn(i):
            if i.operands and i.operands[0].type == x86.X86_OP_IMM:
                targets.add(i.operands[0].imm & 0xFFFF)
        pc += i.size

    labels = {t: f"L_{t:04X}" for t in targets if a <= t < b}
    for s, name in procs.items():
        labels[s] = name
    for x, y, k in data_ranges:
        labels.setdefault(x, f"T_{x:04X}")
    externs = {}
    dvars = set()

    def mem_text(i, op):
        m = op.mem
        seg = i.reg_name(m.segment) if m.segment else None
        parts = []
        if m.base:
            parts.append(i.reg_name(m.base))
        if m.index:
            parts.append(i.reg_name(m.index))
        disp = m.disp & 0xFFFF
        bp_based = m.base == x86.X86_REG_BP
        sym = None
        cs_like = seg == "cs" or (seg is None and any(x <= i.address < y for x, y in dscs))
        if (m.base or m.index) and not bp_based and 0x100 <= disp < 0xFF00:
            if dwin[0] <= disp < dwin[1] and not cs_like:
                sym = f"V_{disp:04X}"
                dvars.add(disp)
            elif cs_like and a <= disp < b:
                sym = labels.setdefault(disp, f"L_{disp:04X}")
            elif seg != "cs":
                sym = f"_D_{disp:04X}"
                externs[sym] = "word"
        elif not (m.base or m.index):
            if cs_like and a <= disp < b:
                sym = labels.setdefault(disp, f"L_{disp:04X}")
            elif dwin[0] <= disp < dwin[1]:
                sym = f"V_{disp:04X}"
                dvars.add(disp)
            else:
                sym = f"_D_{disp:04X}"
                externs[sym] = "word" if op.size == 2 else "byte"
        inner = "+".join(parts)
        if sym:
            inner = f"{inner}+{sym}" if inner else sym
        elif m.disp:
            d = m.disp if m.disp < 0x8000 else m.disp - 0x10000
            inner += (f"+{hx(d)}" if d > 0 else f"-{hx(-d)}") if inner else hx(disp)
        elif bp_based and not m.index:
            inner += "+0"   # [bp] always carries a disp8
        size = {1: "byte ptr ", 2: "word ptr ", 4: "dword ptr "}.get(op.size, "")
        return f"{size}{seg + ':' if seg else ''}[{inner}]"

    out = []
    for kind, item in insns:
        if kind == "data":
            x, y, k = item
            out.append(f"{labels[x]}:")
            if k == "dw":
                ws = [struct.unpack_from('<H', lm, p)[0] for p in range(x, y, 2)]
                for n in range(0, len(ws), 8):
                    out.append("\t\tdw\t" + ",".join(hx(w) for w in ws[n:n + 8]))
            else:
                bs = lm[x:y]
                for n in range(0, len(bs), 12):
                    out.append("\t\tdb\t" + ",".join(hx(v) for v in bs[n:n + 12]))
            continue
        if kind == "byte":
            out.append(f"\t\tdb\t{hx(lm[item])}\t; ??? {item:04x}")
            continue
        i = item
        if i.address in procs:
            out.append(f"\n; {procs[i.address]}")
        if i.address in labels:
            out.append(f"{labels[i.address]}:")
        mn = i.mnemonic
        ops = []
        if mn.startswith("rep ") or mn.startswith("repne ") or mn.startswith("repe "):
            pre, mn2 = mn.split(" ", 1)
            text = f"{pre}\t{mn2}"
            out.append(f"\t\t{text}\t\t; {i.address:04x}")
            continue
        if mn in STRING_OPS:
            out.append(f"\t\t{mn}\t\t\t; {i.address:04x}")
            continue
        if mn == "xlatb":
            out.append(f"\t\txlat\t\t\t; {i.address:04x}")
            continue
        if mn == "lcall":
            mn = "call"
        if mn == "ljmp":
            mn = "jmp"
        is_branch = is_branch_insn(i)
        for n, op in enumerate(i.operands):
            if op.type == x86.X86_OP_REG:
                ops.append(i.reg_name(op.reg))
            elif op.type == x86.X86_OP_IMM:
                v = op.imm & (0xFF if op.size == 1 else 0xFFFF)
                if is_branch:
                    t = op.imm & 0xFFFF
                    name = labels.get(t, f"_F_{t + HDR:04X}")
                    if mn == "jmp" and i.size == 2 and t > i.address:
                        nop = lm[i.address + 2] == 0x90
                        ops.append(name if nop else f"short {name}")
                    elif mn == "jmp" and i.size == 3 and -128 <= t - (i.address + 2) <= 127:
                        ops.append(f"near ptr {name}")
                    else:
                        ops.append(name)
                    if mn == "call" and not (a <= t < b):
                        externs[name] = "near"
                elif any(i.address < r < i.address + i.size for r in relocs):
                    ops.append("DGROUP")
                else:
                    sv = op.imm if op.imm < 0 and op.size == 1 or i.bytes[0] == 0x83 else None
                    ops.append(str(sv) if sv is not None and sv < 0 else hx(v))
            elif op.type == x86.X86_OP_MEM:
                ops.append(mem_text(i, op))
        if mn == "call" and i.operands and i.operands[0].type == x86.X86_OP_MEM and i.bytes[-3] == 0x1E:
            ops[0] = ops[0].replace("word ptr", "dword ptr")
        # skip a NOP that follows a forward short jmp (TASM one-pass emits it)
        if mn == "nop" and out and "\tjmp\t" in out[-1] and "short" not in out[-1]:
            out[-1] += "  ; +nop"
            continue
        out.append(f"\t\t{mn}\t{', '.join(ops)}\t\t; {i.address:04x}")

    print("; draft generated by tools/asm_skeleton.py")
    for name, kind in sorted(externs.items()):
        print(f"\t\textrn\t{name}:{kind}")
    if dvars:
        print("; module DGROUP variables referenced:", " ".join(f"{v:04x}" for v in sorted(dvars)))
    print("\n".join(out))


if __name__ == "__main__":
    main()
