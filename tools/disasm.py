"""Disassemble a CS range of build/DAVE_unpacked.exe with symbol annotations.

Usage: python tools/disasm.py <cs_start> [<cs_end>] | --fn F_XXXX
Calls/jumps to known symbols and DS operands are annotated.
"""
import json, pathlib, re, sys
import capstone
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from symbols import SymbolMap, HDR

def main():
    args = sys.argv[1:]
    census = json.loads((ROOT / "docs" / "function-census.json").read_text())
    if args[0] == "--fn":
        f = next(f for f in census["functions"] if f["id"].upper() == args[1].upper())
        a, b = f["cs_start"], f["cs_end"]
        tables = {t["cs"]: t["entries"] for t in f["jump_tables"]}
    else:
        a = int(args[0], 16); b = int(args[1], 16) if len(args) > 1 else a + 0x80
        tables = {}
    names = {v: k for k, v in SymbolMap().code.items()}
    for f in census["functions"]:
        names.setdefault(f["cs_start"], f["id"])
    lm = (ROOT / "build" / "DAVE_unpacked.exe").read_bytes()[HDR:]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    pc = a
    while pc < b:
        if pc in tables:
            n = tables[pc]
            ws = [int.from_bytes(lm[pc + 2*k:pc + 2*k + 2], "little") for k in range(n)]
            print(f"{pc:04x} table[{n}]: " + " ".join(f"{w:04x}" for w in ws))
            pc += 2 * n; continue
        i = next(md.disasm(lm[pc:pc + 16], pc, 1), None)
        if i is None:
            print(f"{pc:04x} db {lm[pc]:02x}"); pc += 1; continue
        note = ""
        if i.mnemonic in ("call", "jmp") and i.op_str.startswith("0x"):
            t = int(i.op_str, 16) & 0xFFFF
            if t in names: note = f"  ; {names[t]}"
        print(f"{pc:04x} {i.bytes.hex():14s} {i.mnemonic} {i.op_str}{note}")
        pc += i.size

if __name__ == "__main__":
    main()
