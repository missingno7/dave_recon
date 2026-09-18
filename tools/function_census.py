"""Initial function census over RAW_LOAD_MODULE.

Resolves the _main disassembly-boundary mystery (see docs/function-census.md)
and performs a conservative function census: candidate function starts are
found by scanning for the standard Turbo C++ 1.00 small-model prologue byte
pattern `55 8B EC` (push bp; mov bp,sp), each function body is linearly
disassembled forward (capstone, 16-bit mode) until a RET/RETF is reached (or
the next candidate start, whichever comes first, as a safety cap), and CALL
targets + notable idioms (imul by small constants, etc.) are recorded.

This is intentionally conservative/heuristic (per docs/matching-phase.md
phase-3 "function census" frontier) -- it is NOT a claim of matching-C
correctness for any function. Only F_XXXX address-based names are assigned.

Usage:
    "/c/Users/Jiri/AppData/Local/Programs/Python/Python312/python.exe" \
        tools/function_census.py

Writes docs/function-census.json.
"""
import json
import pathlib
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_16

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import coordinates as coord  # noqa: E402

EXE = ROOT / "build" / "DAVE_unpacked.exe"

RAW_LOAD_MODULE_START = 1081       # file offset, per layout/manifest.json (== 0x439)
RAW_LOAD_MODULE_END = 172848       # file offset (end of file)
SEGMENT_BASE = coord.MZ_HEADER_SIZE  # file offset of CS:IP=0000:0000 (program entry point)

assert RAW_LOAD_MODULE_START == 0x439, "RAW_LOAD_MODULE_START must match the manifest's _main anchor"

PROLOGUE = b"\x55\x8b\xec"          # push bp; mov bp, sp


def find_prologue_starts(data: bytes, lo: int, hi: int):
    starts = []
    p = lo
    while True:
        p = data.find(PROLOGUE, p, hi)
        if p == -1:
            break
        starts.append(p)
        p += 1
    return starts


def disassemble_function(md, data: bytes, start: int, next_start: int, hard_end: int):
    """Linearly disassemble one function starting at `start`.

    Stops at the first RET (0xC3/0xC2 imm16) or RETF (0xCB/0xCA imm16)
    encountered, capped at `next_start` (the next candidate prologue) or
    `hard_end`, whichever is smaller, to avoid running into unrelated code
    if this function has no reachable RET within a sane distance.
    """
    cap = min(next_start, hard_end)
    calls = []
    notes = []
    has_sub_sp = False
    end = None
    # capstone must be given addresses relative to the CODE segment's own
    # base (file offset 512, where CS:IP=0000:0000 at the program entry
    # point -- see docs/startup-binding-evidence.json) so that self-relative
    # CALL/JMP rel16 targets resolve correctly. Passing raw file offsets
    # here was the original bug behind the "file offset 0x639" confusion:
    # it silently double-counted the 512-byte header/segment-base offset.
    seg_start = start - SEGMENT_BASE
    insns = list(md.disasm(data[start:cap], seg_start))
    for i, insn in enumerate(insns):
        mnem = insn.mnemonic
        if i <= 3 and mnem == "sub" and insn.op_str.startswith("sp,"):
            has_sub_sp = True
        if mnem == "call" and insn.op_str.startswith("0x"):
            try:
                target_seg = int(insn.op_str, 16) & 0xFFFF
                calls.append(target_seg + SEGMENT_BASE)
            except ValueError:
                pass
        if mnem == "imul":
            notes.append(f"{insn.address + SEGMENT_BASE:#06x}: imul {insn.op_str}")
        if mnem in ("ret", "retf"):
            end = insn.address + insn.size + SEGMENT_BASE
            break
    if end is None:
        # No RET found before the cap; report what we could disassemble.
        end = (insns[-1].address + insns[-1].size + SEGMENT_BASE) if insns else start
        notes.append("no RET found before next candidate/hard end (truncated)")
    return {
        "end": end,
        "has_sub_sp": has_sub_sp,
        "calls": sorted(set(calls)),
        "notes": notes,
        "insn_count": len(insns),
    }


def main():
    data = EXE.read_bytes()
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = False

    starts = find_prologue_starts(data, RAW_LOAD_MODULE_START, RAW_LOAD_MODULE_END)
    functions = []
    for idx, start in enumerate(starts):
        next_start = starts[idx + 1] if idx + 1 < len(starts) else RAW_LOAD_MODULE_END
        info = disassemble_function(md, data, start, next_start, RAW_LOAD_MODULE_END)
        fid = f"F_{start:04X}"
        functions.append({
            "id": fid,
            "start": start,
            "end": info["end"],
            "size": info["end"] - start,
            "has_frame": True,
            "has_sub_sp": info["has_sub_sp"],
            "calls": info["calls"],
            "notes": info["notes"],
            "insn_count": info["insn_count"],
        })

    # Cross-reference: mark call targets that don't land exactly on a known
    # F_XXXX start (helps flag frameless/leaf functions missed by the
    # prologue scan, or misaligned targets worth revisiting).
    starts_set = {f["start"] for f in functions}
    all_calls = sorted({c for f in functions for c in f["calls"]})
    unmatched_call_targets = [c for c in all_calls if c not in starts_set]

    report = {
        "schema": "dave-function-census-v1",
        "source": str(EXE.relative_to(ROOT)).replace("\\", "/"),
        "region": {"start": RAW_LOAD_MODULE_START, "end": RAW_LOAD_MODULE_END},
        "method": "scan for 55 8B EC (push bp; mov bp,sp) prologue bytes as candidate "
                  "function starts; linear capstone disassembly forward from each start "
                  "until the first RET/RETF, capped at the next candidate start.",
        "function_count": len(functions),
        "functions": functions,
        "unmatched_call_targets": unmatched_call_targets,
    }
    out = ROOT / "docs" / "function-census.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"Wrote {out} with {len(functions)} candidate functions "
          f"({len(unmatched_call_targets)} unmatched call targets).")


if __name__ == "__main__":
    main()
