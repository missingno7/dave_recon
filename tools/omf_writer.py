"""Minimal 16-bit OMF (Intel/Microsoft object module) writer, plus a SEGDEF dumper.

Used to produce STAND-IN objects from the original bytes for parts of the
program that are not (yet) built from source -- far data segments, the
data-only module, or any not-yet-reconstructed code -- so that TLINK can
link C0S + the real objects + stand-ins + CS.LIB and the layout of the
whole program emerges from the linker (tools/link_probe.py). It is also what
the final whole-program build will use for data that comes out of the
codecs rather than a compiler.

Records written: THEADR, COMENT (optional), LNAMES, SEGDEF, GRPDEF, EXTDEF,
PUBDEF, LEDATA (chunked to 1024 bytes), FIXUPP (explicit frame/target
methods), MODEND. Everything is 16-bit (no 32-bit record variants).

    w = OmfWriter("FARDATA")
    seg = w.segment("DEMO_FAR", "FAR_DATA", align="para", combine="private",
                    data=blob)
    w.public(seg, "_g_demo_bank", 0)
    path.write_bytes(w.to_bytes())

A segment may have more length than data (`length=`), e.g. _BSS: the
missing tail is uninitialised (TLINK writes zeros or nothing at the end).

Fixups: w.fixup(seg, offset, loc, target, frame=None, self_relative=False)
with loc in {"offset16", "base16", "pointer32", "lobyte"} and target
("segment", seg) / ("group", grp) / ("external", ext); frame defaults to
the target's group for DGROUP members, else the target itself.

    python tools/omf_writer.py --dump some.obj     # list LNAMES/SEGDEF/GRPDEF/PUBDEF/EXTDEF
"""
from __future__ import annotations

import argparse
import pathlib
import struct

THEADR, COMENT, MODEND, EXTDEF, PUBDEF, LNAMES, SEGDEF, GRPDEF, FIXUPP, LEDATA = (
    0x80, 0x88, 0x8A, 0x8C, 0x90, 0x96, 0x98, 0x9A, 0x9C, 0xA0)

ALIGN = {"abs": 0, "byte": 1, "word": 2, "para": 3, "page": 4}
COMBINE = {"private": 0, "public": 2, "stack": 5, "common": 6}
LOC = {"lobyte": 0, "offset16": 1, "base16": 2, "pointer32": 3}


def record(kind: int, body: bytes) -> bytes:
    data = bytes([kind]) + struct.pack("<H", len(body) + 1) + body
    return data + bytes([(-sum(data)) & 0xFF])


def name_bytes(s: str) -> bytes:
    b = s.encode("latin1")
    if len(b) > 255:
        raise ValueError(f"name too long: {s}")
    return bytes([len(b)]) + b


def index(i: int) -> bytes:
    if i < 0x80:
        return bytes([i])
    return bytes([0x80 | (i >> 8), i & 0xFF])


class Segment:
    def __init__(self, idx, name, cls, align, combine, length, data):
        self.idx, self.name, self.cls = idx, name, cls
        self.align, self.combine = align, combine
        self.data = bytes(data or b"")
        self.length = len(self.data) if length is None else length
        if self.length < len(self.data):
            raise ValueError(f"{name}: data longer than the segment")
        if self.length > 0xFFFF:
            raise ValueError(f"{name}: {self.length} bytes do not fit a 16-bit SEGDEF")


class OmfWriter:
    def __init__(self, module: str):
        self.module = module
        self.lnames: list[str] = [""]          # index 1 = "" (unused name slot)
        self.segments: list[Segment] = []
        self.groups: list[tuple[str, list]] = []
        self.publics: list[tuple] = []          # (segment, name, offset)
        self.externals: list[str] = []
        self.fixups: list[tuple] = []
        self.comments: list[bytes] = []

    def _lname(self, s: str) -> int:
        if s not in self.lnames:
            self.lnames.append(s)
        return self.lnames.index(s) + 1

    def segment(self, name, cls, align="para", combine="public", data=b"", length=None) -> Segment:
        seg = Segment(len(self.segments) + 1, name, cls, align, combine, length, data)
        self._lname(name); self._lname(cls)
        self.segments.append(seg)
        return seg

    def group(self, name: str, segments) -> int:
        self._lname(name)
        self.groups.append((name, list(segments)))
        return len(self.groups)

    def public(self, seg: Segment, name: str, offset: int):
        self.publics.append((seg, name, offset))

    def external(self, name: str) -> int:
        if name not in self.externals:
            self.externals.append(name)
        return self.externals.index(name) + 1

    def fixup(self, seg: Segment, offset: int, loc: str, target, frame=None, self_relative=False):
        self.fixups.append((seg, offset, loc, target, frame, self_relative))

    def comment(self, cls: int, text: bytes):
        self.comments.append(bytes([0x00, cls]) + text)

    # ------------------------------------------------------------------
    def _group_of(self, seg: Segment):
        for gi, (_, segs) in enumerate(self.groups, 1):
            if seg in segs:
                return gi
        return None

    def _fixupp(self, fixups) -> bytes:
        body = b""
        for seg, offset, loc, target, frame, self_rel in fixups:
            locat = 0x8000 | (0 if self_rel else 0x4000) | (LOC[loc] << 10) | (offset & 0x3FF)
            kind, ref = target
            if kind == "segment":
                tmethod, tidx = 0, ref.idx
            elif kind == "group":
                tmethod, tidx = 1, ref
            elif kind == "external":
                tmethod, tidx = 2, self.external(ref)
            else:
                raise ValueError(kind)
            if frame is None:
                if kind == "segment" and self._group_of(ref):
                    frame = ("group", self._group_of(ref))
                elif kind == "group":
                    frame = ("group", ref)
                else:
                    frame = ("target", None)
            fkind, fref = frame
            if fkind == "segment":
                fmethod, fidx = 0, fref.idx
            elif fkind == "group":
                fmethod, fidx = 1, fref
            elif fkind == "external":
                fmethod, fidx = 2, self.external(fref)
            elif fkind == "target":
                fmethod, fidx = 5, None
            else:
                raise ValueError(fkind)
            fixdat = (fmethod << 4) | tmethod      # P = 1 is not used: displacement present
            body += struct.pack(">H", locat) + bytes([fixdat])
            if fidx is not None:
                body += index(fidx)
            body += index(tidx) + struct.pack("<H", 0)
        return body

    def to_bytes(self) -> bytes:
        out = record(THEADR, name_bytes(self.module))
        for c in self.comments:
            out += record(COMENT, c)
        # make sure all names are registered before LNAMES is written
        for g, _ in self.groups:
            self._lname(g)
        out += record(LNAMES, b"".join(name_bytes(n) for n in self.lnames))
        for s in self.segments:
            acbp = (ALIGN[s.align] << 5) | (COMBINE[s.combine] << 2)
            length = s.length
            if length == 0x10000:
                acbp |= 0x02
                length = 0
            out += record(SEGDEF, bytes([acbp]) + struct.pack("<H", length)
                          + index(self.lnames.index(s.name) + 1)
                          + index(self.lnames.index(s.cls) + 1) + index(1))
        for name, segs in self.groups:
            body = index(self.lnames.index(name) + 1)
            for s in segs:
                body += b"\xFF" + index(s.idx)
            out += record(GRPDEF, body)
        if self.externals or any(t[0] == "external" for _, _, _, t, _, _ in self.fixups):
            for _, _, _, t, f, _ in self.fixups:
                if t[0] == "external":
                    self.external(t[1])
            out += record(EXTDEF, b"".join(name_bytes(e) + b"\x00" for e in self.externals))
        by_seg = {}
        for seg, name, off in self.publics:
            by_seg.setdefault(seg.idx, []).append((name, off))
        for sidx, pubs in by_seg.items():
            seg = self.segments[sidx - 1]
            grp = self._group_of(seg) or 0
            body = index(grp) + index(sidx)
            for name, off in pubs:
                body += name_bytes(name) + struct.pack("<H", off) + b"\x00"
            out += record(PUBDEF, body)
        for s in self.segments:
            seg_fixups = sorted((f for f in self.fixups if f[0] is s), key=lambda f: f[1])
            for start in range(0, len(s.data), 1024):
                chunk = s.data[start:start + 1024]
                out += record(LEDATA, index(s.idx) + struct.pack("<H", start) + chunk)
                fx = [(seg, off - start, loc, t, fr, sr) for seg, off, loc, t, fr, sr in seg_fixups
                      if start <= off < start + len(chunk)]
                if fx:
                    out += record(FIXUPP, self._fixupp(fx))
        out += record(MODEND, b"\x00")
        return out


# ---------------------------------------------------------------- dumper
def dump(data: bytes) -> list:
    """Human-readable LNAMES/SEGDEF/GRPDEF/PUBDEF/EXTDEF of an object."""
    lines, lnames, segs, grps = [], [], [], []
    at = 0

    def idx(body, i):
        if body[i] & 0x80:
            return ((body[i] & 0x7F) << 8) | body[i + 1], i + 2
        return body[i], i + 1
    while at < len(data):
        kind = data[at]
        ln = struct.unpack_from("<H", data, at + 1)[0]
        body = data[at + 3:at + 2 + ln]
        at += 3 + ln
        if kind == THEADR:
            lines.append(f"THEADR {body[1:1 + body[0]].decode('latin1')}")
        elif kind == LNAMES:
            i = 0
            while i < len(body):
                lnames.append(body[i + 1:i + 1 + body[i]].decode("latin1")); i += 1 + body[i]
        elif kind in (SEGDEF, SEGDEF + 1):
            acbp = body[0]; i = 1
            if acbp >> 5 == 0:
                i += 3
            length = struct.unpack_from("<H", body, i)[0]; i += 2
            n, i = idx(body, i); c, i = idx(body, i)
            if acbp & 2:
                length = 0x10000
            segs.append(lnames[n - 1])
            align = {v: k for k, v in ALIGN.items()}.get(acbp >> 5, acbp >> 5)
            comb = {v: k for k, v in COMBINE.items()}.get((acbp >> 2) & 7, (acbp >> 2) & 7)
            lines.append(f"SEGDEF {lnames[n - 1]:12s} class {lnames[c - 1]:10s} {align:5s} {comb:7s} len {length:#06x}")
        elif kind == GRPDEF:
            n, i = idx(body, 0); members = []
            while i < len(body):
                s, i = idx(body, i + 1); members.append(segs[s - 1])
            grps.append(lnames[n - 1])
            lines.append(f"GRPDEF {lnames[n - 1]} = {', '.join(members)}")
        elif kind in (PUBDEF, PUBDEF + 1):
            g, i = idx(body, 0); s, i = idx(body, i)
            if g == 0 and s == 0:
                i += 2
            while i < len(body):
                name = body[i + 1:i + 1 + body[i]].decode("latin1"); i += 1 + body[i]
                off = struct.unpack_from("<H", body, i)[0]; i += 2
                _, i = idx(body, i)
                lines.append(f"PUBDEF {name} = {segs[s - 1] if s else '?'}:{off:#06x}")
        elif kind == EXTDEF:
            i = 0
            while i < len(body):
                lines.append(f"EXTDEF {body[i + 1:i + 1 + body[i]].decode('latin1')}")
                i += 1 + body[i]; _, i = idx(body, i)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=pathlib.Path)
    args = ap.parse_args()
    if args.dump:
        print("\n".join(dump(args.dump.read_bytes())))


if __name__ == "__main__":
    main()
