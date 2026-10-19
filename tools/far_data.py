"""The game's far data segments, derived from the MZ relocation table.

Shared by the structured-data codecs (sounds.py, demos.py, picfiles.py,
tilesets.py). Nothing is hard-coded but the order in which the segments occur.

How the bounds are derived (docs/data-layout.md section 1):

* Every MZ relocation patches a segment paragraph the program addresses. The
  distinct relocated values are 0x0000 (_TEXT), the seven far data segments,
  _INIT_ and DGROUP.
* DGROUP is the relocated `mov dx,DGROUP` at C0S's entry point
  (levels.dgroup_paragraph). _INIT_ is the segment C0S loads into DS before its
  startup walk (`mov ax,SEG; mov ds,ax; mov si,..; mov di,..; call`).
* The far data segments are the relocated values strictly between 0 and
  _INIT_. Each one ends where the next one (or _INIT_) begins, so a segment's
  extent includes its trailing paragraph-alignment padding.

Segment order (verified by content, see each codec):
    0 demos        attract-mode recordings      (F_519B, F_09DE, F_4A27)
    1 tileset_cga  RLE CGA tileset              (F_1321 case 1)
    2 tileset_vga  RLE VGA tileset              (F_1321 case 3)
    3 sounds       SPK PC-speaker sound bank    (F_519B -> g_sound_data)
    4 picfile_cga  config-screen font + icons   (F_1321 -> F_6099)
    5 picfile_ega
    6 picfile_vga
"""
from __future__ import annotations

import json
import pathlib
import re
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DEFAULT_EXE = ROOT / "build" / "DAVE_unpacked.exe"

import levels  # noqa: E402  (MZ helpers + DGROUP derivation)

SEGMENT_NAMES = ["demos", "tileset_cga", "tileset_vga", "sounds",
                 "picfile_cga", "picfile_ega", "picfile_vga"]

_INIT_WALK = re.compile(rb"\xb8(..)\x8e\xd8\xbe(..)\xbf(..)\xe8", re.S)


def relocated_values(exe: bytes) -> set:
    hdr = levels.header_size(exe)
    return {struct.unpack_from("<H", exe, hdr + lm)[0] for lm in levels.relocation_sites(exe)}


def init_paragraph(exe: bytes) -> int:
    """The _INIT_ segment: C0S does `mov ax,_INIT_; mov ds,ax; mov si,..; mov di,..; call walk`."""
    hdr = levels.header_size(exe)
    ip, cs = struct.unpack_from("<HH", exe, 0x14)
    entry = hdr + cs * 16 + ip
    segs = {struct.unpack("<H", m.group(1))[0] for m in _INIT_WALK.finditer(exe, entry, entry + 0x200)}
    if len(segs) != 1:
        raise ValueError(f"expected one _INIT_ walk segment in C0S, found {sorted(segs)}")
    seg = segs.pop()
    if seg not in relocated_values(exe):
        raise ValueError("_INIT_ paragraph is not a relocated value")
    return seg


def far_segments(exe: bytes) -> list:
    """[{name, paragraph, start, end}] (file offsets) for the seven far data segments."""
    hdr = levels.header_size(exe)
    init = init_paragraph(exe)
    dgroup = levels.dgroup_paragraph(exe)
    if init >= dgroup:
        raise ValueError("_INIT_ must precede DGROUP")
    paras = sorted(v for v in relocated_values(exe) if 0 < v < init)
    if len(paras) != len(SEGMENT_NAMES):
        raise ValueError(f"expected {len(SEGMENT_NAMES)} far data segments, found {len(paras)}")
    bounds = paras + [init]
    return [{"name": n, "paragraph": p, "start": hdr + p * 16, "end": hdr + bounds[i + 1] * 16}
            for i, (n, p) in enumerate(zip(SEGMENT_NAMES, paras))]


def segment(exe: bytes, name: str) -> dict:
    for s in far_segments(exe):
        if s["name"] == name:
            return s
    raise KeyError(name)


def segment_bytes(exe: bytes, name: str) -> bytes:
    s = segment(exe, name)
    return exe[s["start"]:s["end"]]


def extent(name: str, exe_path: pathlib.Path = DEFAULT_EXE):
    s = segment(exe_path.read_bytes(), name)
    return s["start"], s["end"]


def dumps(obj, indent: int = 1) -> str:
    """JSON with one-line lists of scalars (divisor lists, rows), else indented."""
    def enc(o, level):
        pad = " " * (indent * (level + 1))
        end = " " * (indent * level)
        if isinstance(o, dict):
            if not o:
                return "{}"
            items = [f"{pad}{json.dumps(k)}: {enc(v, level + 1)}" for k, v in o.items()]
            return "{\n" + ",\n".join(items) + "\n" + end + "}"
        if isinstance(o, list):
            if all(not isinstance(v, (dict, list)) for v in o):
                return json.dumps(o, separators=(",", ":"))
            return "[\n" + ",\n".join(pad + enc(v, level + 1) for v in o) + "\n" + end + "]"
        return json.dumps(o)
    return enc(obj, 0) + "\n"


def split_zero_padding(blob: bytes, data_len: int) -> int:
    """Number of trailing alignment bytes after `data_len`; they must all be zero."""
    pad = blob[data_len:]
    if any(pad):
        raise ValueError("segment padding is not all zero")
    return len(pad)
