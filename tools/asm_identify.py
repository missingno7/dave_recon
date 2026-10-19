"""Reproduce the assembler-identification evidence recorded in layout/assembler.json.

1. Runs a small MASM/TASM-compatible probe through every candidate assembler
   in tools/asm.py KEYS (installed under toolchain/ASM/<KEY>/) and prints the
   bytes of each discriminating construct next to the bytes the game has.
2. Optionally (--modules) re-matches src/asm/*.asm with every TASM version
   and with multi-pass /m2, through tools/match_asm.py.

Usage: python tools/asm_identify.py [--modules]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import asm  # noqa: E402
import omf  # noqa: E402

# Each construct sits between two `int 3` markers (CC) so it can be cut out.
PROBE = """\
DGROUP  group   _DATA
_DATA   segment word public 'DATA'
oldint  dd      0
_DATA   ends
_TEXT   segment word public 'CODE'
        assume  cs:_TEXT, ds:DGROUP
p1      proc    near
        int     3
        jmp     fwd1            ; forward jmp to a near label
fwd1:   int     3
        pushf                   ; forward far call into the same segment
        call    far ptr isr
        int     3
        cmp     si, FWDC        ; forward-referenced EQU immediate
        int     3
        xchg    si, di          ; operand order -> ModRM
        int     3
        ret
p1      endp
isr     proc    far
        iret
isr     endp
FWDC    equ     0
_TEXT   ends
        end
"""

# what the game has for each construct (and where)
GAME = [
    ("forward jmp near label", "eb0190", "cs 747a: eb 10 90 (EB xx 90)"),
    ("pushf + forward call far ptr", "9c0ee8xxxx90", "cs 750a: 9c 0e e8 0a 00 90"),
    ("cmp si, <forward EQU 0>", "83fe0090", "no instance in the game"),
    ("xchg si, di", "87f7", "cs 7cd7: 87 f7"),
]


def constructs(text: bytes) -> list:
    parts = text.split(b"\xcc")
    return [p.hex() for p in parts[1:5]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", action="store_true")
    args = ap.parse_args()
    work = ROOT / "build" / "asm_identify"
    work.mkdir(parents=True, exist_ok=True)
    probe = work / "probe.asm"
    probe.write_text(PROBE)
    rows = {}
    for key in asm.KEYS:
        if not (ROOT / "toolchain" / "ASM" / key / asm.KEYS[key][0]).exists():
            continue
        obj = asm.assemble_many([probe], key, "", work=work / key)[0]
        if obj is None:
            rows[key] = ["(assembly failed)"] * 4
            continue
        rows[key] = constructs(omf.OmfReader().read(obj.read_bytes(), key).segment_bytes("_TEXT"))
    for n, (what, _, game) in enumerate(GAME):
        print(f"{what}   [game: {game}]")
        for key, got in rows.items():
            print(f"    {key:8s} {got[n]}")
    if args.modules:
        import match_asm
        sources = sorted((ROOT / "src" / "asm").glob("*.asm"))
        for key, opts in [("TASM100", "/mx"), ("TASM101", "/mx"), ("TASM200", "/mx"),
                          ("TASM201", "/mx"), ("TASM200", "/mx /m2")]:
            for r in match_asm.assemble_and_match(sources, work=work / "modules", key=key,
                                                  options=opts):
                print(f"{key} {opts:8s} {r['source']}: {r['verdict']} "
                      f"({r.get('diff_count', '?')} differing bytes, "
                      f"{len(r.get('missing_mz_relocations', []))} base16 fixups off a relocation)")


if __name__ == "__main__":
    main()
