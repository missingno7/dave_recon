"""Codec for the attract-mode demo recordings in far segment 0x0B31.

Evidence (docs/data-layout.md): F_519B sets g_demo_data (DS:0x57A4) =
MK_FP(0x0B31,0). F_09DE picks `rand() % count`, sets g_demo_pos = offsets[i],
loads g_current_level from the first byte and sets g_demo_mode = 1. Each game
frame F_4A27 consumes the stream:

    0x20 n   idle: the counter DS:0x6544 = n; the n following frames get
             "no direction, no buttons" (the frame that reads 0x20 itself keeps
             the live input, which is empty during a demo)
    0x30     end of demo: g_demo_mode++ (the stream position is NOT advanced,
             so whatever follows 0x30 is never read)
    other    one frame of input: low nibble = direction, bit 7 = button 1,
             bit 6 = button 2

Direction codes are the ones the keyboard reader F_63AF produces from the
(dy,dx) of the pressed keys: 0 N, 1 NE, 2 E, 3 SE, 4 S, 5 SW, 6 W, 7 NW,
8 none (verified from its 9-entry jump table at file 0x64F3). Button 1 is the
key in DS:0x1318 (default scan code 0x1D, Ctrl), button 2 the key in DS:0x1319
(default 0x38, Alt).

Byte layout:
    +0          u32  count (5)
    +4          u32  offsets[count], from the segment start; offsets[0] = 4+4*count
    offsets[i]  u8   start level index (0-based g_current_level)
                ...  input stream, terminated by 0x30
                ...  unread bytes after 0x30 up to the next demo (one byte each
                     in this specimen; recorder leftovers, kept verbatim)
    then        zero padding to the segment end

Representation (build/demos/demos.json): per demo the start level and a list
of events, each a string:
    "E x16"          16 consecutive frames of direction E (16 identical bytes)
    "none+alt x2"    direction 8 with button 2 held, 2 frames
    "W+ctrl x1"      ...
    "idle 21"        the 0x20 21 opcode
Runs of identical input bytes are written as one event; the encoder emits one
byte per frame, so the stream is reproduced exactly.

Usage:
    python tools/demos.py decode [--out build/demos]
    python tools/demos.py check
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import far_data  # noqa: E402

SEGMENT = "demos"
OP_IDLE = 0x20
OP_END = 0x30
BUTTON1 = 0x80   # DS:0x1318, default Ctrl
BUTTON2 = 0x40   # DS:0x1319, default Alt
DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "none"]
OUT_DIR = ROOT / "build" / "demos"

_EVENT = re.compile(r"^(?P<dir>[A-Za-z]+|raw:0x[0-9a-fA-F]{2})(?P<mods>(\+ctrl|\+alt)*) x(?P<n>\d+)$")


def input_name(b: int) -> str:
    """Name an input byte; anything outside the known bit layout is kept raw."""
    d = b & 0x0F
    if b & 0x30 or d >= len(DIRECTIONS):
        return f"raw:0x{b:02x}"
    return DIRECTIONS[d] + ("+ctrl" if b & BUTTON1 else "") + ("+alt" if b & BUTTON2 else "")


def input_byte(name: str, mods: str) -> int:
    if name.startswith("raw:"):
        if mods:
            raise ValueError("raw input bytes take no modifiers")
        return int(name[4:], 16)
    b = DIRECTIONS.index(name)
    if "+ctrl" in mods:
        b |= BUTTON1
    if "+alt" in mods:
        b |= BUTTON2
    return b


def decode_stream(data: bytes) -> tuple:
    """(events, index just after the 0x30 terminator)."""
    events = []
    i = 0
    while True:
        b = data[i]
        if b == OP_END:
            return events, i + 1
        if b == OP_IDLE:
            events.append(f"idle {data[i + 1]}")
            i += 2
            continue
        n = 1
        while data[i + n] == b:
            n += 1
        events.append(f"{input_name(b)} x{n}")
        i += n


def encode_stream(events: list) -> bytes:
    out = bytearray()
    for ev in events:
        if ev.startswith("idle "):
            n = int(ev[5:])
            if not 0 <= n <= 0xFF:
                raise ValueError(f"idle count {n} out of range")
            out += bytes([OP_IDLE, n])
            continue
        m = _EVENT.match(ev)
        if not m:
            raise ValueError(f"bad demo event {ev!r}")
        b = input_byte(m["dir"], m["mods"] or "")
        if b in (OP_IDLE, OP_END):
            raise ValueError(f"input byte {b:#x} collides with an opcode")
        out += bytes([b]) * int(m["n"])
    return bytes(out + bytes([OP_END]))


def decode(blob: bytes) -> dict:
    count = struct.unpack_from("<I", blob, 0)[0]
    offsets = list(struct.unpack_from(f"<{count}I", blob, 4))
    if offsets[0] != 4 + 4 * count or offsets != sorted(offsets):
        raise ValueError("demo offset table is not contiguous after the header")
    data_end = len(blob.rstrip(b"\0"))
    demos = []
    for i, off in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < count else data_end
        events, used = decode_stream(blob[off + 1:end])
        demos.append({"index": i, "start_level_index": blob[off], "events": events,
                      "unread_after_end_hex": blob[off + 1 + used:end].hex()})
    return {"format": "dave-demos-v1", "demos": demos,
            "segment_padding_zero_bytes": far_data.split_zero_padding(blob, data_end)}


def encode(d: dict) -> bytes:
    demos = d["demos"]
    bodies = [bytes([x["start_level_index"]]) + encode_stream(x["events"])
              + bytes.fromhex(x["unread_after_end_hex"]) for x in demos]
    out = bytearray(struct.pack("<I", len(bodies)))
    cursor = 4 + 4 * len(bodies)
    for body in bodies:
        out += struct.pack("<I", cursor)
        cursor += len(body)
    for body in bodies:
        out += body
    return bytes(out) + bytes(d["segment_padding_zero_bytes"])


def materialise(out: pathlib.Path = OUT_DIR, exe_path: pathlib.Path = far_data.DEFAULT_EXE) -> pathlib.Path:
    d = decode(far_data.segment_bytes(exe_path.read_bytes(), SEGMENT))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "demos.json"
    path.write_text(far_data.dumps(d))
    return path


def generate(out: pathlib.Path = OUT_DIR) -> bytes:
    path = out / "demos.json"
    if not path.exists():
        materialise(out)
    return encode(json.loads(path.read_text()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["decode", "check"])
    ap.add_argument("--exe", default=str(far_data.DEFAULT_EXE))
    ap.add_argument("--out", default=str(OUT_DIR))
    a = ap.parse_args(argv)
    exe = pathlib.Path(a.exe)
    if a.cmd == "decode":
        print("wrote", materialise(pathlib.Path(a.out), exe))
        return 0
    blob = far_data.segment_bytes(exe.read_bytes(), SEGMENT)
    ok = encode(json.loads(json.dumps(decode(blob)))) == blob
    print("round trip:", "EXACT" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
