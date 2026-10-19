"""Codec for the three config-screen "picfiles" (far segments 0x1D58 / 0x1E84 / 0x20CC).

F_1321 passes MK_FP(seg,0) of the picfile for the current video mode
(g_video_mode 1 CGA / 2 EGA / 3 VGA) to F_6099, which reads the header:

    +0x00  far charptr     8x8 font
    +0x04  far tileptr     16x16 tiles (none here: tileptr == picptr)
    +0x08  far picptr      pictures
    +0x0C  far spriteptr   sprites (none here: it marks the end of the pictures)
           F_6099 stores these to DS:0x8A16/0x8A2E/0x8A1E/0x8A1A. For EGA they
           are used as-is (A200:0000.. = latched EGA video memory, the data is
           copied there plane by plane); for CGA/VGA the segment word is added
           to the picfile's own paragraph.
    +0x10  far pictable    (seg-relative) -> +0x28; F_6099 copies 64 x 16 bytes
                           of it to DS:0x8604
    +0x14  far spritetable (seg-relative) -> +0xF8; 32 x 32 bytes copied to
                           DS:0x65FC (there are no sprites; it points at the fill)
    +0x18  far planes[4]   (seg-relative) plane buffers -> g_pic_planes DS:0x65A8.
                           Only EGA has 4 planes in the file; CGA/VGA hold one,
                           and planes[1..3] point past the segment end.
    +0x28  pictable[13]    u16 width_bytes (per plane), u16 height, u32 offset
                           (from picptr), char name[8] (NUL, '-' fill, NUL)
    +0xF8  8 x '*'         header fill (where the empty sprite table starts)
    +0x100 plane data      per plane: font (128 chars) then the 13 pictures

Pixel formats: CGA 2bpp packed (4 px/byte), EGA 4 separate 1bpp planes
(plane p = bit p of the colour index), VGA 8bpp (1 px/byte); all MSB-first.

Representation (build/picfile_<mode>/): picfile.json (every header field by
name, picture list), font.png (16x8 grid of 8x8 characters) and one PNG per
picture under pics/. PNG pixel values are the colour indices.

Usage:
    python tools/picfiles.py decode [--mode cga|ega|vga|all]
    python tools/picfiles.py check
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

MODES = {"cga": {"bpp": 2, "planes": 1}, "ega": {"bpp": 1, "planes": 4}, "vga": {"bpp": 8, "planes": 1}}
HEADER_PTRS = ["charptr", "tileptr", "picptr", "spriteptr", "pictable", "spritetable"]
PLANE_PTRS = 0x18
ENTRY = 16
CHAR = 8
FONT_COLUMNS = 16


def _lin(ptr: str) -> int:
    seg, off = (int(x, 16) for x in ptr.split(":"))
    return seg * 16 + off


def canonical_name_field(name: str) -> bytes:
    f = (name.encode("ascii") + b"\0").ljust(7, b"-")
    return f if len(f) == 8 else f + b"\0"


def _layout(h: dict, bpp: int):
    """Byte layout within one plane, from the header pointers."""
    base = _lin(h["charptr"])
    font = _lin(h["tileptr"]) - base
    if _lin(h["picptr"]) != _lin(h["tileptr"]):
        raise ValueError("picfile has 16x16 tiles; not supported (none in this game)")
    char_bytes = CHAR * CHAR * bpp // 8
    nchars, rem = divmod(font, char_bytes)
    if rem:
        raise ValueError("font area is not a whole number of characters")
    return {"pics_at": _lin(h["picptr"]) - base, "plane_size": _lin(h["spriteptr"]) - base,
            "char_bytes": char_bytes, "chars": nchars,
            "header_size": _lin(h["planes"][0])}


def _palette(mode: str, exe: bytes):
    return {"cga": pixels.CGA_PALETTE, "ega": pixels.ega_palette(), "vga": pixels.vga_palette(exe)}[mode]


def _to_px(planes, width_bytes: int, rows: int, bpp: int):
    width = width_bytes * 8 // bpp
    if len(planes) == 1:
        return pixels.unpack(planes[0], width, rows, bpp)
    bits = [pixels.unpack(p, width, rows, 1) for p in planes]
    return [[sum(bits[p][y][x] << p for p in range(len(planes))) for x in range(width)] for y in range(rows)]


def _from_px(px, width_bytes: int, rows: int, bpp: int, nplanes: int):
    width = width_bytes * 8 // bpp
    if nplanes == 1:
        return [pixels.pack(px, width, rows, bpp)]
    return [pixels.pack([[(v >> p) & 1 for v in row] for row in px], width, rows, 1) for p in range(nplanes)]


def decode(blob: bytes, mode: str, out: pathlib.Path, palette) -> dict:
    """Write font.png + pics/*.png under `out`; return the JSON description."""
    m = MODES[mode]
    h = {name: pixels.far_ptr(blob, 4 * i) for i, name in enumerate(HEADER_PTRS)}
    h["planes"] = [pixels.far_ptr(blob, PLANE_PTRS + 4 * i) for i in range(4)]
    lay = _layout(h, m["bpp"])
    pt, st = _lin(h["pictable"]), _lin(h["spritetable"])
    if pt != PLANE_PTRS + 16:
        raise ValueError("pictable does not follow the plane pointers")
    npics, rem = divmod(st - pt, ENTRY)
    if rem:
        raise ValueError("pictable does not end on an entry boundary")
    h["tail_hex"] = blob[st:lay["header_size"]].hex()
    nplanes, rem = divmod(len(blob) - lay["header_size"], lay["plane_size"])
    if rem or nplanes != m["planes"]:
        raise ValueError(f"segment holds {nplanes} planes (+{rem} bytes), expected {m['planes']}")
    planes = [blob[lay["header_size"] + p * lay["plane_size"]:][:lay["plane_size"]] for p in range(nplanes)]

    cb = lay["char_bytes"]
    chars = [_to_px([pl[c * cb:(c + 1) * cb] for pl in planes], CHAR * m["bpp"] // 8, CHAR, m["bpp"])
             for c in range(lay["chars"])]
    pixels.write_png(pixels.grid(chars, FONT_COLUMNS, CHAR, CHAR), out / "font.png", palette)

    pics = []
    cursor = 0
    for k in range(npics):
        wb, ht, off, name = struct.unpack_from("<HHI8s", blob, pt + ENTRY * k)
        if off != cursor:
            raise ValueError(f"picture {k} at {off:#x}, expected contiguous {cursor:#x}")
        size = wb * ht
        a = lay["pics_at"] + off
        px = _to_px([pl[a:a + size] for pl in planes], wb, ht, m["bpp"])
        nm = name.split(b"\0")[0].decode("ascii")
        fname = f"pics/{k:02d}_{nm}.png"
        pixels.write_png(px, out / fname, palette)
        e = {"index": k, "name": nm, "width_bytes": wb, "height": ht, "file": fname}
        if name != canonical_name_field(nm):
            e["name_field_hex"] = name.hex()
        pics.append(e)
        cursor += size
    if lay["pics_at"] + cursor != lay["plane_size"]:
        raise ValueError("pictures do not fill the plane up to spriteptr")
    return {"format": "dave-picfile-v1", "mode": mode, "header": h,
            "font": {"file": "font.png", "chars": lay["chars"], "columns": FONT_COLUMNS, "cell": [CHAR, CHAR]},
            "pictures": pics, "planes_in_file": nplanes}


def encode(d: dict, src: pathlib.Path) -> bytes:
    m = MODES[d["mode"]]
    h = d["header"]
    lay = _layout(h, m["bpp"])
    nplanes = d["planes_in_file"]
    header = b"".join(pixels.pack_far_ptr(h[n]) for n in HEADER_PTRS)
    header += b"".join(pixels.pack_far_ptr(p) for p in h["planes"])
    if len(header) != _lin(h["pictable"]):
        raise ValueError("pictable pointer does not match the header layout")
    plane_bufs = [bytearray() for _ in range(nplanes)]

    f = d["font"]
    cells = pixels.ungrid(pixels.read_png(src / f["file"], f["columns"] * CHAR,
                                          -(-f["chars"] // f["columns"]) * CHAR),
                          f["chars"], f["columns"], CHAR, CHAR)
    for cell in cells:
        for p, chunk in enumerate(_from_px(cell, CHAR * m["bpp"] // 8, CHAR, m["bpp"], nplanes)):
            plane_bufs[p] += chunk
    if len(plane_bufs[0]) != lay["pics_at"]:
        raise ValueError("font size does not match tileptr/picptr")

    offset = 0
    for e in d["pictures"]:
        wb, ht = e["width_bytes"], e["height"]
        px = pixels.read_png(src / e["file"], wb * 8 // m["bpp"], ht)
        for p, chunk in enumerate(_from_px(px, wb, ht, m["bpp"], nplanes)):
            plane_bufs[p] += chunk
        name = bytes.fromhex(e["name_field_hex"]) if "name_field_hex" in e else canonical_name_field(e["name"])
        header += struct.pack("<HHI", wb, ht, offset) + name
        offset += wb * ht
    if len(header) != _lin(h["spritetable"]):
        raise ValueError("spritetable pointer does not match the pictable size")
    header += bytes.fromhex(h["tail_hex"])
    if len(header) != lay["header_size"]:
        raise ValueError("header does not end where plane 0 begins")
    if any(len(b) != lay["plane_size"] for b in plane_bufs):
        raise ValueError("plane contents do not end at spriteptr")
    return header + b"".join(plane_bufs)


def out_dir(mode: str) -> pathlib.Path:
    return ROOT / "build" / f"picfile_{mode}"


def materialise(mode: str, out: pathlib.Path = None, exe_path: pathlib.Path = far_data.DEFAULT_EXE):
    exe = exe_path.read_bytes()
    out = out or out_dir(mode)
    out.mkdir(parents=True, exist_ok=True)
    d = decode(far_data.segment_bytes(exe, f"picfile_{mode}"), mode, out, _palette(mode, exe))
    (out / "picfile.json").write_text(far_data.dumps(d))
    return out / "picfile.json"


def generate(mode: str, out: pathlib.Path = None) -> bytes:
    out = out or out_dir(mode)
    if not (out / "picfile.json").exists():
        materialise(mode, out)
    return encode(json.loads((out / "picfile.json").read_text()), out)


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
        ok = generate(mode) == far_data.segment_bytes(exe, f"picfile_{mode}")
        print(f"{mode}: round trip", "EXACT" if ok else "MISMATCH")
        rc |= not ok
    return rc


if __name__ == "__main__":
    sys.exit(main())
