"""Codec for g_vga_palette: the 256-colour VGA palette at DS:0x143A.

768 bytes = 256 x (R, G, B), each a 6-bit VGA DAC value (0..63). set_video_mode
(src/HARDWARE.C, F_6D64) loads all 256 DAC registers from it with INT 10h
AX=1012h when entering mode 13h. Representation: build/palette.json, a list
of 256 [r, g, b] triples.

    python tools/palette.py decode | encode | check
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXE = ROOT / "build" / "DAVE_unpacked.exe"
DS_OFFSET = 0x143A
DGROUP_FILE = 0x200 + 0x254D * 16
SIZE = 768
REPR = ROOT / "build" / "palette.json"


def extent():
    a = DGROUP_FILE + DS_OFFSET
    return a, a + SIZE


def decode(raw: bytes) -> list:
    if any(v > 63 for v in raw):
        raise ValueError("not a 6-bit VGA palette")
    return [list(raw[i:i + 3]) for i in range(0, SIZE, 3)]


def encode(colours: list) -> bytes:
    if len(colours) != 256 or any(len(c) != 3 or not all(0 <= v <= 63 for v in c) for c in colours):
        raise ValueError("palette must be 256 [r,g,b] triples of 6-bit values")
    return bytes(v for c in colours for v in c)


def generate() -> bytes:
    if not REPR.exists():
        a, b = extent()
        REPR.write_text(json.dumps(decode(EXE.read_bytes()[a:b])))
    return encode(json.loads(REPR.read_text()))


if __name__ == "__main__":
    a, b = extent()
    if sys.argv[1:2] == ["decode"]:
        REPR.write_text(json.dumps(decode(EXE.read_bytes()[a:b])))
    elif sys.argv[1:2] == ["encode"]:
        sys.stdout.buffer.write(generate())
    else:
        ok = encode(decode(EXE.read_bytes()[a:b])) == EXE.read_bytes()[a:b]
        print("round trip:", "EXACT" if ok else "MISMATCH")
        sys.exit(0 if ok else 1)
