"""Decoder / encoder / renderer for Dangerous Dave's in-EXE level array (g_levels).

Everything here is derived from build/DAVE_unpacked.exe at run time; no
derived game data is committed. See docs/data-layout.md section "g_levels" for
the full evidence trail. Summary of what the code proves:

* C0S startup loads DS with the relocated paragraph at load-module 0x0001
  (`ba 4d 25  mov dx,DGROUP`), so DGROUP = 0x254D and DS:0 = file 0x256D0.
* A tiny assembly stub (file 0x8516, census-unlisted, called once from game
  init F_519B) does
      mov ax,0x173A ; mov [0x13AC],ax ; mov ax,DGROUP ; mov [0x13AE],ax ; ret
  i.e. `g_levels = MK_FP(DGROUP, 0x173A)`. The `mov ax,DGROUP` immediate is an
  MZ relocation target (load-module 0x831D), proving the segment is DGROUP.
* Level loader F_4E69: `g_level = (char near *)g_levels_off + level*0x500`
  (`mov ax,[0x56F4]; mov dx,0x500; imul dx; mov dx,[0x13AC]; add dx,ax`),
  tiles read at `[g_level + 0x100 + i]` for i in 0..999 (`cmp si,0x3E8`),
  then `g_level_path = MK_FP(DS, g_level)` and `g_level += 0x100`, and
  `movmem(g_level, &g_tiles[0] /* DS:0x615C */, 1000)`.
* Tile neighbours are read at +1 / +0x64 / +0x65 (F_3FD5) -> row stride 100.
* Monster path reader F_2D87 restarts a path when `path[i] == 0xEA`.

Record layout (stride 0x500 = 1280 bytes, 10 records, DS:0x173A..0x493A):
    +0x000  256 bytes   monster path: signed (dx,dy) byte pairs, 0xEA in the
                        dx slot terminates; bytes after the terminator (and the
                        whole path of monster-less levels) are never read and
                        hold editor leftovers, preserved verbatim.
    +0x100  1000 bytes  tile map, 10 rows x 100 columns, row-major, one tile
                        index (0..52, an EGADAVE.DAV fixed-tile index) per byte.
    +0x4E8  24 bytes    never read by the game (record padding to 0x500);
                        preserved verbatim.

Usage:
    python tools/levels.py decode [--exe build/DAVE_unpacked.exe] [--out build/levels]
    python tools/levels.py encode --in build/levels [--exe ...] --out build/DAVE_relevels.exe
    python tools/levels.py render [--egadave assets/EGADAVE.DAV] [--out build/levels]
    python tools/levels.py check      # decode -> encode round trip, byte-exact
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_EXE = ROOT / "build" / "DAVE_unpacked.exe"
DEFAULT_EGADAVE = ROOT / "assets" / "EGADAVE.DAV"

MZ_PARAGRAPH = 16
NUM_LEVELS = 10
RECORD_SIZE = 0x500
PATH_SIZE = 0x100
WIDTH = 100
HEIGHT = 10
TILES_SIZE = WIDTH * HEIGHT
TAIL_SIZE = RECORD_SIZE - PATH_SIZE - TILES_SIZE  # 24
PATH_TERMINATOR = 0xEA

# The asm stub that initialises the far pointer g_levels (file 0x8516):
#   b8 LL HH        mov ax, <levels offset>
#   a3 ac 13        mov [0x13ac], ax
#   b8 SS SS        mov ax, <DGROUP>   (relocated)
#   a3 ae 13        mov [0x13ae], ax
#   c3              ret
STUB_PREFIX_AFTER_IMM = bytes.fromhex("a3ac13b8")
STUB_SUFFIX = bytes.fromhex("a3ae13c3")


def header_size(exe: bytes) -> int:
    if exe[:2] != b"MZ":
        raise ValueError("not an MZ executable")
    return struct.unpack_from("<H", exe, 8)[0] * MZ_PARAGRAPH


def relocation_sites(exe: bytes):
    """Load-module offsets of every MZ relocation target."""
    count = struct.unpack_from("<H", exe, 6)[0]
    table = struct.unpack_from("<H", exe, 0x18)[0]
    sites = []
    for i in range(count):
        off, seg = struct.unpack_from("<HH", exe, table + 4 * i)
        sites.append(seg * MZ_PARAGRAPH + off)
    return sites


def dgroup_paragraph(exe: bytes) -> int:
    """C0S begins `mov dx, DGROUP` (ba lo hi) at the entry point, relocated."""
    hdr = header_size(exe)
    ip, cs = struct.unpack_from("<HH", exe, 0x14)
    entry = hdr + cs * MZ_PARAGRAPH + ip
    if exe[entry] != 0xBA:
        raise ValueError("entry point does not start with mov dx,imm16")
    if (entry + 1 - hdr) not in relocation_sites(exe):
        raise ValueError("DGROUP immediate at entry is not relocated")
    return struct.unpack_from("<H", exe, entry + 1)[0]


def find_levels_base(exe: bytes):
    """Return (ds_offset, file_offset, stub_file_offset) of g_levels, from code."""
    hdr = header_size(exe)
    dgroup = dgroup_paragraph(exe)
    hits = []
    start = 0
    while True:
        i = exe.find(STUB_PREFIX_AFTER_IMM, start)
        if i < 0:
            break
        start = i + 1
        stub = i - 3
        if stub < hdr or exe[stub] != 0xB8:
            continue
        if exe[stub + 9: stub + 9 + len(STUB_SUFFIX)] != STUB_SUFFIX:
            continue
        seg = struct.unpack_from("<H", exe, stub + 7)[0]
        if seg != dgroup or (stub + 7 - hdr) not in relocation_sites(exe):
            continue
        hits.append(stub)
    if len(hits) != 1:
        raise ValueError(f"expected exactly one g_levels init stub, found {len(hits)}")
    stub = hits[0]
    ds_off = struct.unpack_from("<H", exe, stub + 1)[0]
    file_off = hdr + dgroup * MZ_PARAGRAPH + ds_off
    return ds_off, file_off, stub


def _s8(b: int) -> int:
    return b - 256 if b >= 128 else b


def decode_path(raw: bytes) -> dict:
    """Split the 256-byte path into the moves the game reads + unread remainder."""
    moves = []
    i = 0
    terminated = False
    while i + 1 < len(raw):
        if raw[i] == PATH_TERMINATOR:
            terminated = True
            break
        moves.append([_s8(raw[i]), _s8(raw[i + 1])])
        i += 2
    out = {"moves": moves}
    if terminated:
        out["terminator_hex"] = raw[i:i + 2].hex()
        out["unread_hex"] = raw[i + 2:].hex()
    else:
        out["terminator_hex"] = None
        out["unread_hex"] = raw[i:].hex()
    return out


def encode_path(p: dict) -> bytes:
    out = bytearray()
    for dx, dy in p["moves"]:
        out += bytes([dx & 0xFF, dy & 0xFF])
    if p.get("terminator_hex"):
        out += bytes.fromhex(p["terminator_hex"])
    out += bytes.fromhex(p["unread_hex"])
    if len(out) != PATH_SIZE:
        raise ValueError(f"path encodes to {len(out)} bytes, expected {PATH_SIZE}")
    return bytes(out)


def decode_record(rec: bytes, index: int) -> dict:
    assert len(rec) == RECORD_SIZE
    tiles = rec[PATH_SIZE:PATH_SIZE + TILES_SIZE]
    return {
        "level": index + 1,
        "index": index,
        "path": decode_path(rec[:PATH_SIZE]),
        "tiles": [list(tiles[r * WIDTH:(r + 1) * WIDTH]) for r in range(HEIGHT)],
        "unread_tail_hex": rec[PATH_SIZE + TILES_SIZE:].hex(),
    }


def encode_record(d: dict) -> bytes:
    out = bytearray(encode_path(d["path"]))
    if len(d["tiles"]) != HEIGHT or any(len(r) != WIDTH for r in d["tiles"]):
        raise ValueError("tiles must be 10 rows of 100")
    for row in d["tiles"]:
        out += bytes(row)
    out += bytes.fromhex(d["unread_tail_hex"])
    if len(out) != RECORD_SIZE:
        raise ValueError(f"record encodes to {len(out)} bytes")
    return bytes(out)


def decode_levels(exe: bytes) -> list:
    _, base, _ = find_levels_base(exe)
    return [decode_record(exe[base + i * RECORD_SIZE: base + (i + 1) * RECORD_SIZE], i)
            for i in range(NUM_LEVELS)]


def encode_levels(levels: list) -> bytes:
    if len(levels) != NUM_LEVELS:
        raise ValueError("need exactly 10 levels")
    return b"".join(encode_record(d) for d in sorted(levels, key=lambda d: d["index"]))


def patch_exe(exe: bytes, levels: list) -> bytes:
    _, base, _ = find_levels_base(exe)
    blob = encode_levels(levels)
    return exe[:base] + blob + exe[base + len(blob):]


def tiles_text(d: dict) -> str:
    """Human-readable grid: two hex digits per tile, '..' for tile 0."""
    return "\n".join(" ".join(".." if t == 0 else f"{t:02x}" for t in row)
                     for row in d["tiles"]) + "\n"


def render_level(d: dict, egadave: bytes, path: pathlib.Path):
    sys.path.insert(0, str(ROOT / "tools"))
    import egadave_decode as ega
    from PIL import Image
    count, offsets = ega.read_header_and_table(egadave)
    bounds = ega.resource_bounds(offsets, count, len(egadave))
    tiles = {}
    img = Image.new("P", (WIDTH * 16, HEIGHT * 16))
    img.putpalette(ega.flat_palette())
    for r, row in enumerate(d["tiles"]):
        for c, t in enumerate(row):
            if t not in tiles:
                s, e = bounds[t]
                meta, px = ega.decode_resource(egadave, t, s, e)
                if meta["kind"] != "FIXED_TILE_16x16":
                    raise ValueError(f"tile {t} is not a fixed 16x16 tile")
                tile = Image.new("P", (16, 16))
                tile.putpalette(ega.flat_palette())
                tile.putdata([v for prow in px for v in prow])
                tiles[t] = tile
            img.paste(tiles[t], (c * 16, r * 16))
    img.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["decode", "encode", "render", "check", "info"])
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--egadave", default=str(DEFAULT_EGADAVE))
    ap.add_argument("--in", dest="inp", default=str(ROOT / "build" / "levels"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    exe = pathlib.Path(a.exe).read_bytes()
    if a.cmd == "info":
        ds_off, fo, stub = find_levels_base(exe)
        dg = dgroup_paragraph(exe)
        print(f"DGROUP=0x{dg:04X}  g_levels=DS:0x{ds_off:04X} = file 0x{fo:X} "
              f"(init stub at file 0x{stub:X}); {NUM_LEVELS} x 0x{RECORD_SIZE:X} bytes "
              f"-> file 0x{fo:X}..0x{fo + NUM_LEVELS * RECORD_SIZE:X}")
        return 0
    if a.cmd == "decode":
        out = pathlib.Path(a.out or ROOT / "build" / "levels")
        out.mkdir(parents=True, exist_ok=True)
        for d in decode_levels(exe):
            (out / f"level{d['level']:02d}.json").write_text(json.dumps(d, indent=1))
            (out / f"level{d['level']:02d}.txt").write_text(tiles_text(d))
        print(f"wrote {NUM_LEVELS} levels to {out}")
        return 0
    if a.cmd == "encode":
        inp = pathlib.Path(a.inp)
        levels = [json.loads((inp / f"level{i:02d}.json").read_text()) for i in range(1, NUM_LEVELS + 1)]
        out = pathlib.Path(a.out or ROOT / "build" / "DAVE_relevels.exe")
        out.write_bytes(patch_exe(exe, levels))
        print(f"wrote {out}")
        return 0
    if a.cmd == "render":
        out = pathlib.Path(a.out or ROOT / "build" / "levels")
        out.mkdir(parents=True, exist_ok=True)
        ega_bytes = pathlib.Path(a.egadave).read_bytes()
        for d in decode_levels(exe):
            render_level(d, ega_bytes, out / f"level{d['level']:02d}.png")
        print(f"rendered {NUM_LEVELS} levels to {out}")
        return 0
    if a.cmd == "check":
        _, base, _ = find_levels_base(exe)
        levels = json.loads(json.dumps(decode_levels(exe)))  # through JSON
        blob = encode_levels(levels)
        orig = exe[base:base + NUM_LEVELS * RECORD_SIZE]
        ok = blob == orig and patch_exe(exe, levels) == exe
        print("round trip:", "EXACT" if ok else "MISMATCH")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
