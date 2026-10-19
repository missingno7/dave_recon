"""Pixel packing helpers shared by the in-EXE graphics codecs (picfiles.py, tilesets.py).

Conventions (all MSB-first, i.e. the leftmost pixel is in the high bits):
  * packed:  `bpp` bits per pixel, 8/bpp pixels per byte (CGA 2bpp, VGA 8bpp,
             or one EGA bit plane at 1bpp); rows of `width*bpp/8` bytes.
  * PNGs are palette ('P') images whose pixel values ARE the stored indices,
    so a round trip through a PNG is lossless whatever palette is attached.
"""
from __future__ import annotations

import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# CGA palette 1, high intensity (black, light cyan, light magenta, white): the
# usual BIOS mode-4 colours. Only used to make the PNGs viewable.
CGA_PALETTE = [(0, 0, 0), (0x55, 0xFF, 0xFF), (0xFF, 0x55, 0xFF), (0xFF, 0xFF, 0xFF)]


def ega_palette():
    import egadave_decode
    return list(egadave_decode.PALETTE)


def vga_palette(exe: bytes):
    """The game's 256-colour palette g_vga_palette (DS:0x143A, 768 6-bit values),
    which F_6D64 loads with int 10h/AX=1012h."""
    import levels
    base = levels.header_size(exe) + levels.dgroup_paragraph(exe) * 16 + 0x143A
    raw = exe[base:base + 768]
    return [tuple(min(255, v * 255 // 63) for v in raw[i:i + 3]) for i in range(0, 768, 3)]


def unpack(data: bytes, width: int, rows: int, bpp: int):
    """Packed MSB-first pixels -> list of rows of indices."""
    if (width * bpp) % 8:
        raise ValueError("row is not a whole number of bytes")
    bpr = width * bpp // 8
    if len(data) != bpr * rows:
        raise ValueError(f"{len(data)} bytes, expected {bpr * rows}")
    per = 8 // bpp
    mask = (1 << bpp) - 1
    out = []
    for r in range(rows):
        row = []
        for byte in data[r * bpr:(r + 1) * bpr]:
            for k in range(per):
                row.append((byte >> (8 - bpp * (k + 1))) & mask)
        out.append(row)
    return out


def pack(px, width: int, rows: int, bpp: int) -> bytes:
    per = 8 // bpp
    mask = (1 << bpp) - 1
    out = bytearray()
    if len(px) != rows:
        raise ValueError(f"{len(px)} rows, expected {rows}")
    for row in px:
        if len(row) != width:
            raise ValueError(f"row of {len(row)} pixels, expected {width}")
        for x in range(0, width, per):
            byte = 0
            for k in range(per):
                v = row[x + k]
                if v & ~mask:
                    raise ValueError(f"pixel value {v} does not fit in {bpp} bits")
                byte |= v << (8 - bpp * (k + 1))
            out.append(byte)
    return bytes(out)


def write_png(px, path: pathlib.Path, palette):
    from PIL import Image
    h = len(px)
    w = len(px[0]) if h else 0
    img = Image.new("P", (w, h))
    flat = [c for rgb in palette for c in rgb]
    img.putpalette(flat + [0] * (768 - len(flat)))
    img.putdata([v for row in px for v in row])
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def read_png(path: pathlib.Path, width: int, rows: int):
    from PIL import Image
    img = Image.open(path)
    if img.mode != "P":
        raise ValueError(f"{path}: expected a palette PNG, got mode {img.mode}")
    if img.size != (width, rows):
        raise ValueError(f"{path}: size {img.size} != expected {(width, rows)}")
    data = img.tobytes()
    return [list(data[r * width:(r + 1) * width]) for r in range(rows)]


def grid(cells, cols: int, cw: int, ch: int):
    """Lay equal-size cells out in a grid (for font sheets)."""
    rows = (len(cells) + cols - 1) // cols
    out = [[0] * (cols * cw) for _ in range(rows * ch)]
    for i, cell in enumerate(cells):
        gy, gx = divmod(i, cols)
        for y in range(ch):
            out[gy * ch + y][gx * cw:(gx + 1) * cw] = cell[y]
    return out


def ungrid(img, n: int, cols: int, cw: int, ch: int):
    return [[img[(i // cols) * ch + y][(i % cols) * cw:(i % cols + 1) * cw] for y in range(ch)]
            for i in range(n)]


def far_ptr(blob: bytes, at: int) -> str:
    off, seg = struct.unpack_from("<HH", blob, at)
    return f"{seg:04X}:{off:04X}"


def pack_far_ptr(s: str) -> bytes:
    seg, off = (int(x, 16) for x in s.split(":"))
    return struct.pack("<HH", off, seg)
