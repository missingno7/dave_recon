"""Codec for the RLE-compressed CGA and VGA tilesets (far segments 0x0C42 / 0x11EF).

F_1321 (g_video_mode 1 = CGA, 3 = VGA) calls unrle(MK_FP(seg,4), g_tileset,
*(u32 far *)MK_FP(seg,0)) through the asm decoder at 0x7E00/0x7ED4 (tools/rle.py).
EGA loads EGADAVE.DAV instead, which has the same container layout.

Segment layout:
    +0     u32   L = tileset length (the decoder's count)
    +4     ...   RLE stream, exactly as produced by the game's own encoder at
                 0x7F41 (tools/rle.py) run over the tileset with count = L
    then         zero padding to the segment end

The encoder reads past the end of its source buffer (1 byte, plus 1 per
"skip" after a maximal run/literal) and encodes what it finds there; those
chunks lie after the point where the decoder stops, so the game never reads
them. They are kept as `rle.overread_hex`:
    CGA: 1 byte  (0x9A)
    VGA: 22 bytes (1 + 21 skips; the bytes look like x86 code of the tool)
The VGA tileset is longer than 0xFF00 bytes, so the encoder's renormalisation
re-emitted source byte 0xFF00: the stream decodes to the tileset with that
byte duplicated, and the game's copy of every resource from that point on
(the tail of resource 147 and resources 148..157) is shifted by one byte. The
representation keeps the tileset as it was BEFORE compression (all offsets and
sizes self-consistent); the duplication is reproduced by the encoder.

Tileset layout (the same container as EGADAVE.DAV):
    +0          u32  count
    +4          u32  offsets[count] (offsets[0] = 4 + 4*count, contiguous)
    resources   0..52: fixed 16x16 tiles, no header
                        CGA 64 bytes (2bpp), VGA 256 bytes (8bpp)
                53..:  u16 width, u16 height, then pixels, rows of whole bytes:
                        CGA 2bpp, ceil(width/4) bytes x height rows (the
                            blitter at 0x8900 reads exactly that), followed
                            by unread bytes: every CGA sprite is allocated
                            ceil(width/8)*2*(height+1) bytes, EGADAVE.DAV's
                            sprite size rule, and the remainder is leftover
                            (kept verbatim as `unread_tail_hex`)
                        VGA 8bpp, width bytes x height rows, no tail

Representation (build/tileset_<mode>/): tileset.json + one palette PNG per
resource (full padded raster; PNG values are colour indices).

Usage:
    python tools/tilesets.py decode [--mode cga|vga|all]
    python tools/tilesets.py check
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
import pixels  # noqa: E402
import rle  # noqa: E402

MODES = {"cga": {"bpp": 2}, "vga": {"bpp": 8}}
TILE = 16
SOURCE_OFFSET = 0   # offset part of the encoder's source pointer: the only value (of 0..15) that reproduces the VGA stream


def tile_bytes(mode):
    return TILE * TILE * MODES[mode]["bpp"] // 8


def sprite_geometry(mode: str, w: int, h: int):
    """(stored pixel width, rows) of the raster the game's blitter reads: whole
    bytes per row (CGA blitter 0x8900: (w+3)>>2 bytes x h rows)."""
    per = 8 // MODES[mode]["bpp"]
    return -(-w // per) * per, h


def _palette(mode: str, exe: bytes):
    return pixels.CGA_PALETTE if mode == "cga" else pixels.vga_palette(exe)


# ------------------------------------------------------------ tileset <-> files
def decode_tileset(data: bytes, mode: str, out: pathlib.Path, palette) -> list:
    bpp = MODES[mode]["bpp"]
    count = struct.unpack_from("<I", data, 0)[0]
    offsets = list(struct.unpack_from(f"<{count}I", data, 4))
    if offsets[0] != 4 + 4 * count:
        raise ValueError("offset table is not followed directly by resource 0")
    ends = offsets[1:] + [len(data)]
    tb = tile_bytes(mode)
    fixed = 0
    while fixed < count and ends[fixed] - offsets[fixed] == tb:
        fixed += 1
    res = []
    for i, (a, e) in enumerate(zip(offsets, ends)):
        if i < fixed:
            px = pixels.unpack(data[a:e], TILE, TILE, bpp)
            entry = {"index": i, "kind": "tile", "file": f"resources/res_{i:03d}_tile.png"}
        else:
            w, h = struct.unpack_from("<HH", data, a)
            sw, sh = sprite_geometry(mode, w, h)
            n = sw * sh * bpp // 8
            if 4 + n > e - a:
                raise ValueError(f"resource {i}: {e - a} bytes, too small for a {w}x{h} sprite")
            px = pixels.unpack(data[a + 4:a + 4 + n], sw, sh, bpp)
            entry = {"index": i, "kind": "sprite", "width": w, "height": h,
                     "file": f"resources/res_{i:03d}_sprite.png"}
            if a + 4 + n < e:
                entry["unread_tail_hex"] = data[a + 4 + n:e].hex()
        pixels.write_png(px, out / entry["file"], palette)
        res.append(entry)
    return res


def encode_tileset(resources: list, mode: str, src: pathlib.Path) -> bytes:
    bpp = MODES[mode]["bpp"]
    bodies = []
    for r in resources:
        if r["kind"] == "tile":
            bodies.append(pixels.pack(pixels.read_png(src / r["file"], TILE, TILE), TILE, TILE, bpp))
        elif r["kind"] == "sprite":
            sw, sh = sprite_geometry(mode, r["width"], r["height"])
            bodies.append(struct.pack("<HH", r["width"], r["height"])
                          + pixels.pack(pixels.read_png(src / r["file"], sw, sh), sw, sh, bpp)
                          + bytes.fromhex(r.get("unread_tail_hex", "")))
        else:
            raise ValueError(f"unknown resource kind {r['kind']!r}")
    out = bytearray(struct.pack("<I", len(bodies)))
    cursor = 4 + 4 * len(bodies)
    for b in bodies:
        out += struct.pack("<I", cursor)
        cursor += len(b)
    return bytes(out) + b"".join(bodies)


# ------------------------------------------------------------ segment <-> tileset
def split_segment(blob: bytes) -> dict:
    """Undo the compression: recover the source tileset, the encoder's
    over-read bytes and the zero padding; verified by re-encoding."""
    length = struct.unpack_from("<I", blob, 0)[0]
    _, used = rle.decode(blob[4:], length)
    # The encoder's output continues past what the decoder consumes (the
    # over-read chunks). It ends at the first chunk boundary followed only by
    # zero padding.
    decoded = bytearray()
    stream_end = None
    for at, n, chunk in rle.decode_chunks(blob, 4):
        decoded += chunk
        nxt = at + (1 + n if blob[at] >= 0x80 else 2)
        if nxt - 4 >= used and not any(blob[nxt:]):
            stream_end = nxt
            break
    if stream_end is None:
        raise ValueError("RLE stream does not end before zero padding")
    # Undo the renormalisation re-emissions: with the source pointer at offset
    # SOURCE_OFFSET the k-th happens at source index k*0xFF00 - SOURCE_OFFSET.
    source = bytearray(decoded)
    k = 1
    while k * rle.NORMALISE_AT - SOURCE_OFFSET < len(source):
        del source[k * rle.NORMALISE_AT - SOURCE_OFFSET]
        k += 1
    tileset, overread = bytes(source[:length]), bytes(source[length:])
    got = rle.encode(tileset + overread, length, SOURCE_OFFSET)
    if got["stream"] != blob[4:stream_end] or got["read"] != len(tileset) + len(overread):
        raise ValueError("re-encoding with the 0x7F41 encoder does not reproduce the stream")
    return {"tileset": tileset, "overread": overread, "normalised_at": got["normalised_at"],
            "padding": far_data.split_zero_padding(blob, stream_end)}


def join_segment(tileset: bytes, overread: bytes, padding: int) -> bytes:
    """Compress exactly as the original tool did. For the original tileset the
    encoder reads precisely the stored over-read bytes (split_segment checks
    this). An edited tileset can change the number of skips; then the encoder
    reads fewer of them, or zeros beyond them."""
    got = rle.encode(tileset + overread + bytes(0x400), len(tileset), SOURCE_OFFSET)
    return struct.pack("<I", len(tileset)) + got["stream"] + bytes(padding)


# ------------------------------------------------------------ build/ materialisation
def out_dir(mode: str) -> pathlib.Path:
    return ROOT / "build" / f"tileset_{mode}"


def materialise(mode: str, out: pathlib.Path = None, exe_path: pathlib.Path = far_data.DEFAULT_EXE):
    exe = exe_path.read_bytes()
    out = out or out_dir(mode)
    parts = split_segment(far_data.segment_bytes(exe, f"tileset_{mode}"))
    resources = decode_tileset(parts["tileset"], mode, out, _palette(mode, exe))
    d = {"format": "dave-rle-tileset-v1", "mode": mode,
         "fixed_tiles": sum(r["kind"] == "tile" for r in resources),
         "resources": resources,
         "rle": {"encoder": "file 0x7F41 (tools/rle.py)", "source_offset": SOURCE_OFFSET,
                 "overread_hex": parts["overread"].hex(),
                 "duplicated_source_bytes": parts["normalised_at"]},
         "segment_padding_zero_bytes": parts["padding"]}
    (out / "tileset.json").write_text(far_data.dumps(d))
    return out / "tileset.json"


def encode(d: dict, src: pathlib.Path) -> bytes:
    if d["rle"]["source_offset"] != SOURCE_OFFSET:
        raise ValueError("only source_offset 0 is modelled")
    tileset = encode_tileset(d["resources"], d["mode"], src)
    return join_segment(tileset, bytes.fromhex(d["rle"]["overread_hex"]), d["segment_padding_zero_bytes"])


def generate(mode: str, out: pathlib.Path = None) -> bytes:
    out = out or out_dir(mode)
    if not (out / "tileset.json").exists():
        materialise(mode, out)
    return encode(json.loads((out / "tileset.json").read_text()), out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["decode", "check"])
    ap.add_argument("--mode", choices=list(MODES) + ["all"], default="all")
    ap.add_argument("--exe", default=str(far_data.DEFAULT_EXE))
    a = ap.parse_args(argv)
    exe_path = pathlib.Path(a.exe)
    exe = exe_path.read_bytes()
    rc = 0
    for mode in (MODES if a.mode == "all" else [a.mode]):
        path = materialise(mode, None, exe_path)
        if a.cmd == "decode":
            print("wrote", path)
            continue
        ok = generate(mode) == far_data.segment_bytes(exe, f"tileset_{mode}")
        print(f"{mode}: round trip", "EXACT" if ok else "MISMATCH")
        rc |= not ok
    return rc


if __name__ == "__main__":
    sys.exit(main())
