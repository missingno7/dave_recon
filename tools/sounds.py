"""Codec for the PC-speaker sound bank in far segment 0x1C2E (`SPK\\0` format).

Evidence (docs/data-layout.md): F_519B sets g_sound_data (DS:0x137A) =
MK_FP(0x1C2E,0); play_sound F_763E indexes the directory with a 1-based id
(`si = id*16`), reads +2 (priority, compared against the playing sound's),
+0 (data offset, stored as the play pointer DS:0x1388) and +3 (timer rate: when
> 1 the PIT channel 0 is reprogrammed to 0x10000/rate and the BIOS tick is
chained every `rate` interrupts). The timer ISR at 0x7719 walks u16 words from
the play pointer: 0xFFFF ends the sound (0x769B silences the speaker), any
other value is a PIT divisor (0 switches the speaker off for that tick).

Byte layout (all little-endian):
    +0x000  char[4]   magic "SPK\\0"
    +0x004  u32       bank length in bytes (= end of the last sound's data)
    +0x008  8 bytes   reserved, zero in this specimen (kept verbatim)
    +0x010  63 x 16   directory, one entry per sound id 1..63:
                      u16 data offset (from the bank start), u8 priority,
                      u8 rate, char name[12] (NUL-terminated; the bytes after
                      the NUL are editor leftovers, kept verbatim)
    +0x400  ...       sound data, in directory order, contiguous: u16 divisors,
                      each sound terminated by 0xFFFF
    then              zero padding up to the next paragraph (the segment end)

Representation (build/sounds/sounds.json): the header fields, one object per
directory entry with its divisor list, and the padding length. Offsets and the
bank length are re-derived by the encoder (the decoder checks that they are
exactly what the original holds).

Usage:
    python tools/sounds.py decode [--out build/sounds]
    python tools/sounds.py check
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import far_data  # noqa: E402

SEGMENT = "sounds"
MAGIC = b"SPK\0"
HEADER_SIZE = 0x10
ENTRY_SIZE = 16
NAME_SIZE = 12
END = 0xFFFF
OUT_DIR = ROOT / "build" / "sounds"


def decode(blob: bytes) -> dict:
    if blob[:4] != MAGIC:
        raise ValueError("not an SPK bank")
    total = struct.unpack_from("<I", blob, 4)[0]
    first = struct.unpack_from("<H", blob, HEADER_SIZE)[0]
    n_entries, rem = divmod(first - HEADER_SIZE, ENTRY_SIZE)
    if rem:
        raise ValueError("directory does not end on an entry boundary")
    sounds = []
    cursor = first
    for k in range(n_entries):
        off, prio, rate, name = struct.unpack_from("<HBB12s", blob, HEADER_SIZE + ENTRY_SIZE * k)
        if off != cursor:
            raise ValueError(f"sound {k + 1}: data at {off:#x}, expected contiguous {cursor:#x}")
        words = []
        while True:
            w = struct.unpack_from("<H", blob, cursor)[0]
            cursor += 2
            if w == END:
                break
            words.append(w)
        nul = name.index(0)
        entry = {"id": k + 1, "name": name[:nul].decode("ascii"), "priority": prio, "rate": rate,
                 "divisors": words}
        if any(name[nul + 1:]):
            entry["name_tail_hex"] = name[nul + 1:].hex()
        sounds.append(entry)
    if cursor != total:
        raise ValueError(f"sound data ends at {cursor:#x}, header length says {total:#x}")
    return {
        "format": "dave-spk-v1",
        "reserved_hex": blob[8:HEADER_SIZE].hex(),
        "sounds": sounds,
        "segment_padding_zero_bytes": far_data.split_zero_padding(blob, total),
    }


def encode(d: dict) -> bytes:
    sounds = d["sounds"]
    first = HEADER_SIZE + ENTRY_SIZE * len(sounds)
    directory = bytearray()
    data = bytearray()
    for s in sounds:
        name = s["name"].encode("ascii") + b"\0" + bytes.fromhex(s.get("name_tail_hex", ""))
        if len(name) > NAME_SIZE:
            raise ValueError(f"sound {s['id']}: name field longer than {NAME_SIZE} bytes")
        name = name.ljust(NAME_SIZE, b"\0")
        directory += struct.pack("<HBB", first + len(data), s["priority"], s["rate"]) + name
        for w in s["divisors"]:
            if not 0 <= w < END:
                raise ValueError(f"sound {s['id']}: divisor {w} out of range")
            data += struct.pack("<H", w)
        data += struct.pack("<H", END)
    total = first + len(data)
    out = MAGIC + struct.pack("<I", total) + bytes.fromhex(d["reserved_hex"]) + directory + data
    return out + bytes(d["segment_padding_zero_bytes"])


def materialise(out: pathlib.Path = OUT_DIR, exe_path: pathlib.Path = far_data.DEFAULT_EXE) -> pathlib.Path:
    d = decode(far_data.segment_bytes(exe_path.read_bytes(), SEGMENT))
    out.mkdir(parents=True, exist_ok=True)
    path = out / "sounds.json"
    path.write_text(far_data.dumps(d))
    return path


def generate(out: pathlib.Path = OUT_DIR) -> bytes:
    path = out / "sounds.json"
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
