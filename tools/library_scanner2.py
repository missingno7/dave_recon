"""Whole-runtime identification of Dangerous Dave's Turbo C++ 1.00 library code.

Successor to tools/library_scanner.py (left untouched). The first scanner
matched only each CS.LIB module's `_TEXT` bytes against census-anchored
offsets (plus a literal memmem fallback), which structurally missed:

  * every module whose `_TEXT` has fixups and is not exactly the size of a
    census function (census covers only ~2/3 of the bytes, and the library
    area contains functions the call-graph walk never reached);
  * segment-alignment padding (FARHEAP and NEARHEAP are paragraph-aligned,
    leaving 10 and 15 zero bytes that look like "unknown" gaps);
  * modules that contribute *only* to `_DATA` / `_BSS` / `_INIT_`
    (`_streams`, `_openfd`, `_ctype`, `_fmode`, `_stklen`, `_heaplen`): they
    have no `_TEXT` at all, so a `_TEXT`-only scanner cannot see them.

This tool therefore:

1. Parses CS.LIB and C0S.OBJ with a richer OMF reader than tools/omf.py
   (SEGDEF alignment/class, GRPDEF, THREAD records, LEDATA+LIDATA, and
   per-fixup frame/target/displacement), so fixups are *evaluated*, not
   merely masked.
2. Searches every CS.LIB module's `_TEXT` (masked by its own fixup bytes)
   across the whole code area, then requires the hits to tile one contiguous
   run in library-member order, with the gaps between them explained by the
   SEGDEF alignment of the next module (zero-filled padding).
3. Computes the transitive extern closure of the linked modules (plus
   C0S's externs) to find the D/BSS-only modules, and explains why each
   module is linked (which linked module / C0S / game code pulls it).
4. Lays out the `_DATA` / `_INIT_` contributions in library order anchored at
   the end of the file image, byte-compares them (modulo fixups), and infers
   the `_BSS` placement from the fixups that reference it.
5. Re-derives every fixup target (near calls between modules, DGROUP
   offsets, segment bases, `_INIT_` table entries) from the discovered
   layout and compares with the bytes actually present. Each fixup is
   classed verified / mismatch / unverified(reason).
6. Builds the library call-site map for game code.

Proof bar (unchanged): a module is "identified" only if every non-fixup byte
of every segment it contributes to the file image matches exactly.

Usage:
    python tools/library_scanner2.py [--write]

Without --write the report is printed only; with --write it (re)generates
docs/library-map.json and docs/library-map.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from collections import OrderedDict, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402

UNPACKED_PATH = ROOT / "build" / "DAVE_unpacked.exe"
CENSUS_PATH = ROOT / "docs" / "function-census-callgraph-v2.json"  # v2 call-graph census (includes library functions)
PROLOGUE_CENSUS_PATH = ROOT / "docs" / "function-census-prologue-scan.json"
MANIFEST_PATH = ROOT / "layout" / "manifest.json"
LIB_DIR = ROOT / "toolchain" / "LIB"

MZ_HEADER_SIZE = 0x200
C0S_END = 0x439          # file offset where C0S's 569-byte _TEXT ends (== _main)
MAIN_FILE = 0x439

ALIGN_BYTES = {0: 1, 1: 1, 2: 2, 3: 16, 4: 256, 5: 4}   # SEGDEF ACBP A field


# ---------------------------------------------------------------------------
# Rich OMF parser
# ---------------------------------------------------------------------------

class Seg:
    def __init__(self, name, cls, align, comb, length):
        self.name, self.cls, self.align, self.comb, self.length = name, cls, align, comb, length
        self.data = bytearray(length)
        self.defined = bytearray(length)

    def put(self, off, payload):
        end = off + len(payload)
        if end > len(self.data):
            grow = end - len(self.data)
            self.data.extend(b"\0" * grow)
            self.defined.extend(b"\0" * grow)
        self.data[off:end] = payload
        self.defined[off:end] = b"\1" * len(payload)


class Obj:
    """One OMF object module (a CS.LIB member or C0S.OBJ)."""

    def __init__(self, name):
        self.name = name
        self.lnames = []
        self.segs = []          # index 0 == SEGDEF 1
        self.groups = []        # [(name, [seg index 0-based...])]
        self.externs = []
        self.publics = []       # {"name","group","seg"(0-based or None),"offset"}
        self.fixups = []
        self.blob_sha256 = ""
        self.parse_error = None

    def seg_by_name(self, name):
        for i, s in enumerate(self.segs):
            if s.name == name:
                return i
        return None

    def seg_len(self, name):
        i = self.seg_by_name(name)
        return self.segs[i].length if i is not None else 0


def _expand_iterated(body, at):
    repeat, at = struct.unpack_from("<H", body, at)[0], at + 2
    blocks, at = struct.unpack_from("<H", body, at)[0], at + 2
    if blocks == 0:
        n = body[at]
        content = body[at + 1:at + 1 + n]
        return content * repeat, at + 1 + n
    unit = bytearray()
    for _ in range(blocks):
        chunk, at = _expand_iterated(body, at)
        unit.extend(chunk)
    return bytes(unit) * repeat, at


def parse_obj(blob: bytes, label: str = "") -> Obj:
    R = omf.OmfReader
    obj = Obj(label)
    obj.blob_sha256 = hashlib.sha256(blob).hexdigest()
    frame_threads, target_threads = {}, {}
    last = None   # (seg index 0-based, data record offset)
    for kind, body in R.records(blob):
        if kind in R.REFUSED_32:
            raise omf.MatchError(f"32-bit OMF record 0x{kind:02X} in {label}")
        if kind in (R.THEADR, R.LHEADR):
            obj.name = body[1:1 + body[0]].decode("latin1")
        elif kind == R.LNAMES:
            at = 0
            while at < len(body):
                n = body[at]
                obj.lnames.append(body[at + 1:at + 1 + n].decode("latin1"))
                at += 1 + n
        elif kind == R.SEGDEF16:
            acbp = body[0]
            align, comb = acbp >> 5, (acbp >> 2) & 7
            at = 1
            if align == 0:
                at += 3
            length = struct.unpack_from("<H", body, at)[0]
            if (acbp >> 1) & 1:
                length = 0x10000
            at += 2
            ni, at = R._index(body, at)
            ci, at = R._index(body, at)
            obj.segs.append(Seg(obj.lnames[ni - 1], obj.lnames[ci - 1], align, comb, length))
        elif kind == R.GRPDEF:
            ni, at = R._index(body, 0)
            comps = []
            while at < len(body):
                at += 1                      # 0xFF component type
                si, at = R._index(body, at)
                comps.append(si - 1)
            obj.groups.append((obj.lnames[ni - 1], comps))
        elif kind in (R.EXTDEF, R.LEXTDEF):
            at = 0
            while at < len(body):
                n = body[at]
                obj.externs.append(body[at + 1:at + 1 + n].decode("latin1"))
                at += 1 + n
                _, at = R._index(body, at)
        elif kind == R.COMDEF:
            # communal names share the EXTDEF index space; only the count matters here
            at = 0
            def _len_enc(at):
                b = body[at]
                if b < 0x80:
                    return at + 1
                return at + 1 + {0x81: 2, 0x84: 3, 0x88: 4}.get(b, 0)
            while at < len(body):
                n = body[at]
                obj.externs.append(body[at + 1:at + 1 + n].decode("latin1"))
                at += 1 + n
                _, at = R._index(body, at)
                dtype = body[at]
                at += 1
                at = _len_enc(at)
                if dtype == 0x61:
                    at = _len_enc(at)
        elif kind in (R.PUBDEF16, R.LPUBDEF):
            gi, at = R._index(body, 0)
            si, at = R._index(body, at)
            frame = None
            if gi == 0 and si == 0:
                frame = struct.unpack_from("<H", body, at)[0]
                at += 2
            while at < len(body):
                n = body[at]
                name = body[at + 1:at + 1 + n].decode("latin1")
                at += 1 + n
                off = struct.unpack_from("<H", body, at)[0]
                at += 2
                _, at = R._index(body, at)
                obj.publics.append({"name": name, "group": gi - 1 if gi else None,
                                    "seg": si - 1 if si else None, "offset": off,
                                    "abs_frame": frame})
        elif kind == R.LEDATA16:
            si, at = R._index(body, 0)
            off = struct.unpack_from("<H", body, at)[0]
            obj.segs[si - 1].put(off, body[at + 2:])
            last = (si - 1, off)
        elif kind == R.LIDATA16:
            si, at = R._index(body, 0)
            off = struct.unpack_from("<H", body, at)[0]
            at += 2
            payload = bytearray()
            while at < len(body):
                chunk, at = _expand_iterated(body, at)
                payload.extend(chunk)
            obj.segs[si - 1].put(off, bytes(payload))
            last = (si - 1, off)
        elif kind == R.FIXUPP16:
            at = 0
            while at < len(body):
                b0 = body[at]
                if b0 & 0x80:
                    locat = (b0 << 8) | body[at + 1]
                    at += 2
                    loc = (locat >> 10) & 0xF
                    seg_rel = bool((locat >> 14) & 1)
                    data_off = locat & 0x3FF
                    fixdat = body[at]
                    at += 1
                    if (fixdat >> 7) & 1:
                        fm, fd = frame_threads.get((fixdat >> 4) & 3, (None, 0))
                    else:
                        fm = (fixdat >> 4) & 7
                        fd = 0
                        if fm in (0, 1, 2):
                            fd, at = R._index(body, at)
                    if (fixdat >> 3) & 1:
                        tm, td = target_threads.get(fixdat & 3, (None, 0))
                        tm &= 3
                    else:
                        tm = fixdat & 3
                        td, at = R._index(body, at)
                    disp = None
                    if not (fixdat >> 2) & 1:
                        disp = struct.unpack_from("<H", body, at)[0]
                        at += 2
                    if last is None:
                        raise omf.MatchError("FIXUPP before data record")
                    obj.fixups.append({
                        "seg": last[0], "offset": last[1] + data_off, "loc": loc,
                        "width": R.LOC_WIDTH.get(loc, 2), "seg_rel": seg_rel,
                        "frame_method": fm, "frame_datum": fd,
                        "target_method": tm, "target_datum": td,
                        "disp": disp,
                    })
                else:
                    at += 1
                    is_frame = (b0 >> 6) & 1
                    method = (b0 >> 2) & 7
                    num = b0 & 3
                    datum = 0
                    if not (is_frame and method >= 3):
                        datum, at = R._index(body, at)
                    (frame_threads if is_frame else target_threads)[num] = (method, datum)
    return obj


def load_library(path: pathlib.Path):
    reader = omf.OmfReader()
    out = []
    for name, blob in reader.split_library(path.read_bytes()):
        try:
            out.append(parse_obj(blob, name))
        except (IndexError, KeyError, struct.error, omf.MatchError) as exc:
            # C++ stream-library members use COMDAT-style hidden segments this
            # reader does not model; none of them can be a C-only game's link.
            stub = Obj(name)
            stub.parse_error = repr(exc)
            stub.blob_sha256 = hashlib.sha256(blob).hexdigest()
            out.append(stub)
    return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def masked_positions(obj: Obj, seg_i: int):
    """Bytes of segment `seg_i` covered by one of the module's own fixups."""
    m = set()
    for fx in obj.fixups:
        if fx["seg"] == seg_i:
            m.update(range(fx["offset"], fx["offset"] + fx["width"]))
    return m


def find_masked(data: bytes, seg: Seg, mask: set, lo: int, hi: int):
    """All starts in [lo, hi-len] where seg.data matches `data` outside mask."""
    L = len(seg.data)
    # longest unmasked run is the search key
    best, i = (0, 0), 0
    while i < L:
        if i in mask:
            i += 1
            continue
        j = i
        while j < L and j not in mask:
            j += 1
        if j - i > best[1] - best[0]:
            best = (i, j)
        i = j
    s, e = best
    if e - s < 4:
        return None      # too little literal content to search for
    key = bytes(seg.data[s:e])
    hits = []
    p = data.find(key, lo)
    while 0 <= p < hi:
        st = p - s
        if st >= lo and st + L <= hi:
            if all(k in mask or data[st + k] == seg.data[k] for k in range(L)):
                hits.append(st)
        p = data.find(key, p + 1)
    return hits


def align_up(x, a):
    return (x + a - 1) // a * a


def c_name(sym: str) -> str:
    return sym[1:] if sym.startswith("_") and not sym.startswith("__") else sym


# ---------------------------------------------------------------------------
# main analysis
# ---------------------------------------------------------------------------

class Analysis:
    def __init__(self):
        self.data = UNPACKED_PATH.read_bytes()
        manifest = json.loads(MANIFEST_PATH.read_text())
        exp = manifest["unpacked_original"]
        if len(self.data) != exp["size"] or hashlib.md5(self.data).hexdigest() != exp["md5"]:
            raise SystemExit("build/DAVE_unpacked.exe does not match the pinned specimen")
        self.lib_path = LIB_DIR / "CS.LIB"
        self.mods = load_library(self.lib_path)
        self.by_name = {m.name: m for m in self.mods}
        self.index = {m.name: i for i, m in enumerate(self.mods)}
        self.c0s = parse_obj((LIB_DIR / "C0S.OBJ").read_bytes(), "C0S")
        self.lib_sha = hashlib.sha256(self.lib_path.read_bytes()).hexdigest()
        # public symbol -> modules
        self.pubmap = defaultdict(list)
        for m in self.mods:
            for p in m.publics:
                self.pubmap[p["name"]].append(m.name)
        self.c0s_pubs = {p["name"]: p for p in self.c0s.publics}
        self.mz_relocs = self._relocs()
        # DGROUP / IGROUP frame bases (file offsets), from C0S's relocation values
        c0s_reloc_vals = sorted({v for _, v in self.mz_relocs})
        self.dgroup_para = self._read16(self.mz_relocs[0][0]) if self.mz_relocs else None
        self.ds_base = MZ_HEADER_SIZE + self.dgroup_para * 16
        self.notes = []
        self.game_bss_start_file = None
        self.bss_end_file = None

    # -- MZ ---------------------------------------------------------------
    def _read16(self, file_off):
        return struct.unpack_from("<H", self.data, file_off)[0]

    def _relocs(self):
        d = self.data
        n = struct.unpack_from("<H", d, 6)[0]
        ro = struct.unpack_from("<H", d, 24)[0]
        hdr = struct.unpack_from("<H", d, 8)[0] * 16
        out = []
        for i in range(n):
            off, seg = struct.unpack_from("<HH", d, ro + 4 * i)
            f = hdr + seg * 16 + off
            out.append((f, struct.unpack_from("<H", d, f)[0]))
        return out

    # -- step 1: text search ---------------------------------------------
    def search_text(self, lo=C0S_END, hi=0xB600):
        hits = {}
        for m in self.mods:
            si = m.seg_by_name("_TEXT")
            if si is None or not m.segs[si].defined:
                continue
            seg = m.segs[si]
            if m.segs[si].length == 0:
                continue
            mask = masked_positions(m, si)
            h = find_masked(self.data, seg, mask, lo, hi)
            if h:
                hits[m.name] = h
        self.text_hits = hits
        return hits

    # -- step 2: tile ---------------------------------------------------
    def tile(self):
        """Order the hits by address and check they tile one run in library order."""
        flat = sorted((h, n) for n, hs in self.text_hits.items() for h in hs)
        # a module may hit twice (duplicate literal code); keep the one that tiles
        placements, cursor, prev_index = [], None, -1
        problems = []
        i = 0
        # start at the first strong hit
        start = flat[0][0]
        cursor = start
        remaining = list(flat)
        while True:
            cands = [(h, n) for h, n in remaining if h >= cursor]
            if not cands:
                break
            h, n = cands[0]
            m = self.by_name[n]
            si = m.seg_by_name("_TEXT")
            a = ALIGN_BYTES.get(m.segs[si].align, 1)
            expected = align_up(cursor, a) if a > 1 else cursor
            # allow alignment relative to CS (file - 0x200)
            expected = MZ_HEADER_SIZE + align_up(cursor - MZ_HEADER_SIZE, a)
            if h != expected:
                problems.append(f"{n}: hit at {h:#x}, expected {expected:#x} after cursor {cursor:#x} (align {a})")
                break
            pad = h - cursor
            if pad and any(self.data[cursor:h]):
                problems.append(f"{n}: non-zero padding {cursor:#x}..{h:#x}")
            if self.index[n] <= prev_index:
                problems.append(f"{n}: out of library order")
            prev_index = self.index[n]
            L = m.segs[si].length
            placements.append({"module": n, "start": h, "end": h + L, "size": L,
                               "pad_before": pad, "align": a})
            cursor = h + L
        self.text_place = placements
        self.text_end = cursor
        self.tile_problems = problems
        # any hit not used?
        used = {(p["start"], p["module"]) for p in placements}
        self.unused_hits = [(hex(h), n) for h, n in flat if (h, n) not in used]
        return placements

    # -- step 3: closure --------------------------------------------------
    def closure(self):
        text_mods = {p["module"] for p in self.text_place}
        linked = set(text_mods)
        c0pubs = set(self.c0s_pubs)
        # externs the *game* needs are unknown here; closure starts from the
        # text-matched modules and C0S, then adds provider modules.
        need = defaultdict(set)
        for e in self.c0s.externs:
            need[e].add("C0S")
        changed = True
        while changed:
            changed = False
            for n in list(linked):
                for e in self.by_name[n].externs:
                    need[e].add(n)
            for e, who in need.items():
                if e in c0pubs:
                    continue
                for p in self.pubmap.get(e, []):
                    if p not in linked:
                        linked.add(p)
                        changed = True
        self.linked = linked
        self.dbss_only = sorted(linked - text_mods, key=lambda n: self.index[n])
        unresolved = sorted(e for e in need if e not in c0pubs and not self.pubmap.get(e))
        self.unresolved_externs = unresolved
        # who pulls whom
        pulled = defaultdict(set)
        for e, who in need.items():
            for p in self.pubmap.get(e, []):
                for w in who:
                    if w != p:
                        pulled[p].add(w)
        self.pulled_by = pulled
        self.roots = sorted((n for n in linked if not pulled.get(n)),
                            key=lambda n: self.index[n])
        # C0S-pulled
        self.c0s_pulled = {p for e in self.c0s.externs for p in self.pubmap.get(e, [])}

    # -- step 4: data layout ---------------------------------------------
    def layout_data(self):
        order = sorted(self.linked, key=lambda n: self.index[n])
        file_end = len(self.data)
        # _DATA contributions, library order, each aligned per its SEGDEF
        contribs = []
        for n in order:
            m = self.by_name[n]
            si = m.seg_by_name("_DATA")
            if si is not None and m.segs[si].length:
                contribs.append((n, si))
        # sum with alignment, solved from the tail (alignment relative to DS base)
        # forward-simulate from candidate base L0 until total end == file end
        def forward(l0):
            pos, out = l0, []
            for n, si in contribs:
                a = ALIGN_BYTES.get(self.by_name[n].segs[si].align, 1)
                pos = self.ds_base + align_up(pos - self.ds_base, a)
                out.append((n, si, pos))
                pos += self.by_name[n].segs[si].length
            return out, pos
        # find L0 such that end == file_end (monotone in l0 up to alignment)
        total = sum(self.by_name[n].segs[si].length for n, si in contribs)
        cand = None
        for l0 in range(file_end - total - 64, file_end - total + 1):
            if (l0 - self.ds_base) % 2:
                continue
            out, end = forward(l0)
            if end == file_end:
                cand = (l0, out)
        if cand is None:
            self.notes.append("could not anchor _DATA contributions to end-of-file")
            self.data_place, self.lib_data_start = [], None
            return
        l0, out = cand
        self.lib_data_start = l0
        place, prev_end = [], l0
        for n, si, pos in out:
            L = self.by_name[n].segs[si].length
            place.append({"module": n, "start": pos, "end": pos + L, "size": L,
                          "pad_before": pos - prev_end})
            prev_end = pos + L
        self.data_place = place
        # _INIT_ contributions: they sit just below DGROUP (para 0x254C)
        init_mods = [n for n in order
                     if self.by_name[n].seg_by_name("_INIT_") is not None
                     and self.by_name[n].seg_len("_INIT_")]
        total_init = sum(self.by_name[n].seg_len("_INIT_") for n in init_mods)
        init_start = self.ds_base - 16
        pos = init_start
        self.init_place = []
        for n in init_mods:
            L = self.by_name[n].seg_len("_INIT_")
            self.init_place.append({"module": n, "start": pos, "end": pos + L, "size": L})
            pos += L
        self.init_base = init_start
        self.init_end = pos
        # BSS contributions (not in file)
        self.bss_mods = [(n, self.by_name[n].seg_len("_BSS"),
                          ALIGN_BYTES.get(self.by_name[n].segs[self.by_name[n].seg_by_name("_BSS")].align, 1))
                         for n in order if self.by_name[n].seg_len("_BSS")]

    # -- step 5: symbol addresses & fixup verification --------------------
    def text_base(self, name):
        if name == "C0S":
            return MZ_HEADER_SIZE
        for p in self.text_place:
            if p["module"] == name:
                return p["start"]
        return None

    def data_base(self, name):
        if name == "C0S":
            return self.ds_base
        for p in self.data_place:
            if p["module"] == name:
                return p["start"]
        return None

    def init_base_of(self, name):
        if name == "C0S":
            return self.init_base
        for p in self.init_place:
            if p["module"] == name:
                return p["start"]
        return None

    def seg_file_base(self, modname, obj, seg_i):
        """File-offset base of segment `seg_i` of linked module, or None (BSS handled via self.bss_file)."""
        s = obj.segs[seg_i]
        if s.name == "_TEXT":
            return self.text_base(modname)
        if s.name == "_DATA":
            return self.data_base(modname)
        if s.name == "_INIT_":
            return self.init_base_of(modname)
        if s.name == "_INITEND_":
            return self.init_end
        if s.name in ("_EXIT_", "_EXITEND_"):
            return self.init_end   # EXITDATA follows INITDATA (both empty beyond _INIT_)
        if s.name == "_BSS":
            if modname == "C0S":
                return self.game_bss_start_file       # start of all BSS (inferred)
            return self.bss_file.get(modname)
        if s.name == "_BSSEND":
            return self.bss_end_file
        return None

    def frame_base_for_segment(self, segname):
        if segname == "_TEXT":
            return MZ_HEADER_SIZE
        if segname in ("_DATA", "_BSS", "_CVTSEG", "_SCNSEG", "_BSSEND", "_STACK"):
            return self.ds_base
        if segname in ("_INIT_", "_INITEND_", "_EXIT_", "_EXITEND_"):
            return self.init_base
        return None

    def group_base(self, gname):
        return {"DGROUP": self.ds_base, "IGROUP": self.init_base,
                "EGROUP": self.init_base}.get(gname)

    def resolve_symbol(self, name):
        """-> (file offset, segname) of a public symbol, or None. Prefers C0S, then linked libs."""
        if name == "_main":
            return (MAIN_FILE, "_TEXT")
        for owner, obj in [("C0S", self.c0s)] + [(n, self.by_name[n]) for n in
                                                 sorted(self.linked, key=lambda n: self.index[n])]:
            for p in obj.publics:
                if p["name"] == name:
                    if p["seg"] is None:
                        return (p["offset"], "ABS")
                    base = self.seg_file_base(owner, obj, p["seg"])
                    if base is None:
                        return ("unplaced", obj.segs[p["seg"]].name, owner, p["offset"])
                    return (base + p["offset"], obj.segs[p["seg"]].name)
        return None

    def infer_bss(self):
        """Infer each BSS contribution's DGROUP file-base from fixups that target it."""
        self.bss_file = {}
        votes = defaultdict(set)
        owners = [("C0S", self.c0s)] + [(n, self.by_name[n]) for n in self.linked]
        for owner, obj in owners:
            for fx in obj.fixups:
                if fx["target_method"] != 2 or fx["loc"] != 1 or not fx["seg_rel"]:
                    continue
                ext = obj.externs[fx["target_datum"] - 1]
                prov = [p for p in self.pubmap.get(ext, []) if p in self.linked]
                for pm in prov:
                    pobj = self.by_name[pm]
                    for p in pobj.publics:
                        if p["name"] == ext and p["seg"] is not None and pobj.segs[p["seg"]].name == "_BSS":
                            seg = obj.segs[fx["seg"]]
                            orig = struct.unpack_from("<H", seg.data, fx["offset"])[0]
                            fo = self._fixup_file_offset(owner, obj, fx)
                            if fo is None:
                                continue
                            actual = self._read16(fo)
                            # actual = orig + (bssbase_file + p.offset + disp - ds_base)
                            disp = fx["disp"] or 0
                            base = actual - orig - p["offset"] - disp + self.ds_base
                            votes[pm].add(base)
        for pm, vs in votes.items():
            if len(vs) == 1:
                self.bss_file[pm] = next(iter(vs))
            else:
                self.notes.append(f"BSS base of {pm} ambiguous: {sorted(map(hex, vs))}")
        # chain consistency: library order, word aligned, no gaps
        chain_ok, chain = True, []
        known = [(n, sz, al) for n, sz, al in self.bss_mods if n in self.bss_file]
        prev = None
        for n, sz, al in self.bss_mods:
            chain.append({"module": n, "size": sz,
                          "dgroup_offset": (self.bss_file[n] - self.ds_base) if n in self.bss_file else None})
        # fill unknown bases by chain from known neighbours
        for i, (n, sz, al) in enumerate(self.bss_mods):
            if n in self.bss_file:
                continue
            if i > 0 and self.bss_mods[i - 1][0] in self.bss_file:
                pn, psz, _ = self.bss_mods[i - 1]
                self.bss_file[n] = self.ds_base + align_up(self.bss_file[pn] - self.ds_base + psz, al)
                chain[i]["dgroup_offset"] = self.bss_file[n] - self.ds_base
                chain[i]["derived_from_chain"] = True
        for i in range(1, len(self.bss_mods)):
            n, sz, al = self.bss_mods[i]
            pn, psz, _ = self.bss_mods[i - 1]
            if n in self.bss_file and pn in self.bss_file:
                want = self.ds_base + align_up(self.bss_file[pn] - self.ds_base + psz, al)
                if want != self.bss_file[n]:
                    chain_ok = False
        self.bss_chain = chain
        self.bss_chain_ok = chain_ok
        last_n, last_sz, _ = self.bss_mods[-1]
        self.bss_end_file = self.bss_file[last_n] + last_sz     # _BSSEND follows the last contribution
        # C0S's references to its own _BSS (== start of all BSS contributions,
        # i.e. the end of the game's BSS) can only be inferred, not derived.
        c0s_bss = self.c0s.seg_by_name("_BSS")
        starts = set()
        for fx in self.c0s.fixups:
            if fx["target_method"] == 0 and fx["target_datum"] - 1 == c0s_bss and fx["loc"] == 1 and fx["seg_rel"]:
                fo = MZ_HEADER_SIZE + fx["offset"]
                orig = struct.unpack_from("<H", self.c0s.segs[fx["seg"]].data, fx["offset"])[0]
                starts.add(self._read16(fo) - orig - (fx["disp"] or 0) + self.ds_base)
        self.game_bss_start_file = next(iter(starts)) if len(starts) == 1 else None
        if len(starts) > 1:
            self.notes.append(f"C0S _BSS start ambiguous: {sorted(map(hex, starts))}")

    def _fixup_file_offset(self, owner, obj, fx):
        base = self.seg_file_base(owner, obj, fx["seg"])
        return None if base is None else base + fx["offset"]

    def verify_fixups(self):
        """Evaluate every fixup of every linked module (and C0S)."""
        owners = [("C0S", self.c0s)] + [(n, self.by_name[n]) for n in
                                        sorted(self.linked, key=lambda n: self.index[n])]
        self.fixup_report = OrderedDict()
        for owner, obj in owners:
            rep = {"total": 0, "verified": 0, "inferred": 0, "mismatch": 0, "unverified": 0,
                   "mismatches": [], "unverified_reasons": defaultdict(int),
                   "verified_by_kind": defaultdict(int)}
            for fx in obj.fixups:
                rep["total"] += 1
                status, detail = self._eval_fixup(owner, obj, fx)
                if status == "verified":
                    rep["verified"] += 1
                    rep["verified_by_kind"][detail] += 1
                elif status == "inferred":
                    rep["inferred"] += 1
                elif status == "mismatch":
                    rep["mismatch"] += 1
                    rep["mismatches"].append(detail)
                else:
                    rep["unverified"] += 1
                    rep["unverified_reasons"][detail] += 1
            rep["unverified_reasons"] = dict(rep["unverified_reasons"])
            rep["verified_by_kind"] = dict(rep["verified_by_kind"])
            self.fixup_report[owner] = rep

    def _target(self, owner, obj, fx):
        """-> (target file offset, description) or (None, reason)."""
        tm, td = fx["target_method"], fx["target_datum"]
        if tm == 2:                                     # external
            name = obj.externs[td - 1]
            r = self.resolve_symbol(name)
            if r is None:
                return None, f"external {name} not defined in C0S/linked modules/_main"
            if r[0] == "unplaced":
                return None, f"external {name} in unplaced segment {r[1]} of {r[2]}"
            if r[1] == "ABS":
                return None, f"external {name} is absolute"
            tag = " [inferred]" if r[1] == "_BSS" else ""
            return r[0], f"{name}{tag}"
        if tm == 0:                                     # segment
            seg_i = td - 1
            base = self.seg_file_base(owner, obj, seg_i)
            if base is None:
                return None, f"segment {obj.segs[seg_i].name} placement unknown"
            tag = " [inferred]" if obj.segs[seg_i].name == "_BSS" else ""
            return base, f"seg {obj.segs[seg_i].name}{tag}"
        if tm == 1:                                     # group
            gname = obj.groups[td - 1][0]
            base = self.group_base(gname)
            if base is None:
                return None, f"group {gname} unknown"
            return base, f"group {gname}"
        return None, f"target method {tm}"

    def _frame(self, owner, obj, fx, target_desc, target_file):
        fm, fd = fx["frame_method"], fx["frame_datum"]
        if fm == 1:
            return self.group_base(obj.groups[fd - 1][0])
        if fm == 0:
            return self.frame_base_for_segment(obj.segs[fd - 1].name)
        if fm == 4:
            return self.frame_base_for_segment(obj.segs[fx["seg"]].name)
        if fm == 5:                                     # TARGET's frame
            if fx["target_method"] == 1:
                return self.group_base(obj.groups[fx["target_datum"] - 1][0])
            if fx["target_method"] == 0:
                return self.frame_base_for_segment(obj.segs[fx["target_datum"] - 1].name)
            if fx["target_method"] == 2:
                r = self.resolve_symbol(obj.externs[fx["target_datum"] - 1])
                if r and r[0] != "unplaced":
                    return self.frame_base_for_segment(r[1])
        return None

    def _eval_fixup(self, owner, obj, fx):
        fo = self._fixup_file_offset(owner, obj, fx)
        if fo is None:
            return "unverified", f"location segment {obj.segs[fx['seg']].name} has no placement"
        w = fx["width"]
        seg = obj.segs[fx["seg"]]
        tfile, desc = self._target(owner, obj, fx)
        if tfile is None:
            return "unverified", desc
        loc = fx["loc"]
        disp = fx["disp"] or 0
        orig_raw = bytes(seg.data[fx["offset"]:fx["offset"] + w])
        actual_raw = self.data[fo:fo + w]
        frame = self._frame(owner, obj, fx, desc, tfile)
        if loc in (1, 5):                                  # offset16
            orig = struct.unpack("<H", orig_raw)[0]
            actual = struct.unpack("<H", actual_raw)[0]
            if not fx["seg_rel"]:                          # self-relative near
                if self.frame_base_for_segment(seg.name) is None:
                    return "unverified", "self-relative in non-code segment"
                exp = (orig + tfile + disp - (fo + 2)) & 0xFFFF
                kind = "near-rel"
            else:
                if frame is None:
                    return "unverified", f"frame unknown for {desc}"
                exp = (orig + tfile + disp - frame) & 0xFFFF
                kind = "offset16"
        elif loc == 2:                                     # base16 (segment paragraph)
            if frame is None:
                return "unverified", f"frame unknown for {desc}"
            actual = struct.unpack("<H", actual_raw)[0]
            exp = ((frame - MZ_HEADER_SIZE) // 16) & 0xFFFF
            kind = "segment-base"
            if (fo, actual) not in self.mz_relocs:
                return "mismatch", {"at": hex(fo), "why": "base16 location is not in the MZ relocation table"}
        elif loc == 3:                                     # pointer32
            if frame is None:
                return "unverified", f"frame unknown for {desc}"
            orig = struct.unpack_from("<H", orig_raw, 0)[0]
            actual = struct.unpack("<HH", actual_raw)
            exp = ((orig + tfile + disp - frame) & 0xFFFF, ((frame - MZ_HEADER_SIZE) // 16) & 0xFFFF)
            actual = tuple(actual)
            kind = "pointer32"
        elif loc in (0, 4):
            if frame is None:
                return "unverified", f"frame unknown for {desc}"
            orig = orig_raw[0] | 0   # byte addend (assume 0 high)
            v = (tfile + disp - frame + orig) & 0xFFFF
            exp = v & 0xFF if loc == 0 else v >> 8
            actual = actual_raw[0]
            kind = "byte"
        else:
            return "unverified", f"loc {loc} unsupported"
        if exp == actual:
            if "[inferred]" in desc:
                return "inferred", kind       # base was solved from fixups, so not independent
            return "verified", kind
        return "mismatch", {"at": hex(fo), "kind": kind, "target": desc,
                            "expected": exp if isinstance(exp, tuple) else hex(exp),
                            "actual": actual if isinstance(actual, tuple) else hex(actual)}

    # -- step 6: byte verification of each placed contribution ------------
    def verify_bytes(self):
        out = OrderedDict()
        def cmp(owner, obj, seg_i, base):
            seg = obj.segs[seg_i]
            mask = masked_positions(obj, seg_i)
            diffs = [k for k in range(seg.length)
                     if seg.defined[k] and self.data[base + k] != seg.data[k] and k not in mask]
            undef_pos = [k for k in range(seg.length) if not seg.defined[k]]
            undefined = len(undef_pos)
            # bytes the object declares but never initialises (e.g. FARHEAP's
            # ___first/___last/___rover words) must read back as zero
            undef_nonzero = sum(1 for k in undef_pos if self.data[base + k])
            return {"segment": seg.name, "size": seg.length, "start": base, "end": base + seg.length,
                    "fixup_masked_bytes": len(mask), "unexplained_diffs": len(diffs),
                    "undefined_bytes": undefined, "undefined_bytes_nonzero_in_image": undef_nonzero,
                    "exact_nonfixup_bytes": seg.length - len(mask) - undefined - len(diffs)
                    if not diffs else None}
        for p in self.text_place:
            m = self.by_name[p["module"]]
            si = m.seg_by_name("_TEXT")
            out.setdefault(p["module"], {})["_TEXT"] = cmp(p["module"], m, si, p["start"])
        for p in self.data_place:
            m = self.by_name[p["module"]]
            si = m.seg_by_name("_DATA")
            out.setdefault(p["module"], {})["_DATA"] = cmp(p["module"], m, si, p["start"])
        for p in self.init_place:
            m = self.by_name[p["module"]]
            si = m.seg_by_name("_INIT_")
            out.setdefault(p["module"], {})["_INIT_"] = cmp(p["module"], m, si, p["start"])
        self.byte_verify = out

    # -- padding bytes ----------------------------------------------------
    def padding(self):
        pads = []
        for p in self.text_place:
            if p["pad_before"]:
                pads.append({"where": "before " + p["module"] + " _TEXT", "start": p["start"] - p["pad_before"],
                             "end": p["start"], "reason": f"SEGDEF alignment {p['align']}",
                             "all_zero": not any(self.data[p["start"] - p["pad_before"]:p["start"]])})
        for p in self.data_place:
            if p["pad_before"]:
                pads.append({"where": "before " + p["module"] + " _DATA", "start": p["start"] - p["pad_before"],
                             "end": p["start"], "reason": "SEGDEF word alignment",
                             "all_zero": not any(self.data[p["start"] - p["pad_before"]:p["start"]])})
        self.pads = pads

    # -- step 7: game call sites -----------------------------------------
    def name_table(self):
        """code file offset -> list of (symbol, module) for every public entry in a placed _TEXT."""
        table = defaultdict(list)
        for owner, obj in [("C0S", self.c0s)] + [(p["module"], self.by_name[p["module"]]) for p in self.text_place]:
            base = self.text_base(owner)
            for pub in obj.publics:
                if pub["seg"] is not None and obj.segs[pub["seg"]].name == "_TEXT":
                    table[base + pub["offset"]].append((pub["name"], owner))
        # several publics may share an address (near/far aliases): list the near
        # `N_` form first, plain names next, far `F_` aliases last
        def pref(entry):
            n = entry[0]
            return 0 if n.startswith("N_") else (2 if n.startswith("F_") else 1)
        for a in table:
            table[a].sort(key=pref)
        self.names = table
        self.main_names = {MAIN_FILE: [("_main", "GAME")]}

    def call_sites(self):
        """Library call-site map for game code.

        Linear-sweep every game function (census starts plus every 55 8B EC
        prologue and the prologue-scan baseline, each bounded by the next
        start), decoding with capstone at CS offsets so 16-bit wraparound is
        right. A site is a near CALL/JMP (E8/E9) whose target is a placed
        library/C0S byte; it is *named* only when the target is exactly a
        public entry point of a placed module.
        """
        import bisect
        from capstone import Cs, CS_ARCH_X86, CS_MODE_16
        md = Cs(CS_ARCH_X86, CS_MODE_16)
        lib_lo = self.text_place[0]["start"]
        lib_hi = self.text_place[-1]["end"]
        census = json.loads(CENSUS_PATH.read_text())
        census_start = {f["start"]: f for f in census["functions"] if f["start"] < lib_lo}
        starts = set(census_start) | {C0S_END}
        pro = json.loads(PROLOGUE_CENSUS_PATH.read_text())
        for f in pro.get("functions", []):
            s = f.get("start", f.get("file_offset"))
            if s is not None and C0S_END <= s < lib_lo:
                starts.add(s)
        p = self.data.find(b"\x55\x8b\xec", C0S_END, lib_lo)
        while p != -1:
            starts.add(p)
            p = self.data.find(b"\x55\x8b\xec", p + 1, lib_lo)
        starts = sorted(starts)
        bounds = list(zip(starts, starts[1:] + [lib_lo]))

        def owner(off):
            return starts[bisect.bisect_right(starts, off) - 1]

        entries = self.names
        sites, addr_taken, insn_starts = [], [], set()
        for s, e in bounds:
            pos = s
            while pos < e:
                insns = list(md.disasm(self.data[pos:e], pos - MZ_HEADER_SIZE))
                if not insns:
                    pos += 1
                    continue
                for ins in insns:
                    site = ins.address + MZ_HEADER_SIZE
                    insn_starts.add(site)
                    b = self.data[site]
                    if b in (0xE8, 0xE9) and ins.size == 3:
                        rel = struct.unpack_from("<h", self.data, site + 1)[0]
                        tgt = ((ins.address + 3 + rel) & 0xFFFF) + MZ_HEADER_SIZE
                        sites.append({"site": site, "op": "call" if b == 0xE8 else "jmp", "target": tgt})
                    elif b in (0x68, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF) and ins.size == 3:
                        t = struct.unpack_from("<H", self.data, site + 1)[0] + MZ_HEADER_SIZE
                        if lib_lo <= t < lib_hi and t in entries:
                            addr_taken.append({"site": site, "target": t})
                last = insns[-1]
                nxt = last.address + last.size + MZ_HEADER_SIZE
                pos = nxt if nxt > pos else pos + 1
        self.insn_starts = insn_starts
        # also record, for transparency, E8/E9 whose target is an exact library
        # entry but which the sweep did not decode as an instruction start
        swept = {r["site"] for r in sites}
        undecoded = []
        for off in range(C0S_END, lib_lo - 2):
            if self.data[off] == 0xE8 and off not in swept:
                rel = struct.unpack_from("<h", self.data, off + 1)[0]
                tgt = ((off - MZ_HEADER_SIZE + 3 + rel) & 0xFFFF) + MZ_HEADER_SIZE
                if tgt in entries and lib_lo <= tgt < lib_hi and off not in insn_starts:
                    undecoded.append({"site": off, "target": tgt})
        self.undecoded_candidates = undecoded
        res = []
        for st in sites:
            t = st["target"]
            if C0S_END > t >= MZ_HEADER_SIZE:
                region = "C0S"
            elif lib_lo <= t < lib_hi:
                region = "CS.LIB"
            else:
                continue                    # game-internal call
            names = entries.get(t, [])
            own = owner(st["site"])
            res.append({**st, "caller_start": own,
                        "caller_id": census_start[own]["id"] if own in census_start else f"F_{own:04X}",
                        "in_census": own in census_start,
                        "symbols": [n for n, _ in names],
                        "module": names[0][1] if names else None,
                        "region": region})
        self.call_res = res
        self.call_unnamed = [r for r in res if not r["symbols"]]
        # cross-check against the call-graph census's own (E8-resolved) edges
        mine = {(r["site"], r["target"]) for r in res}
        lib_edges = []
        for e in census["call_edges"]:
            cid = e["callee_id"]
            if cid.startswith("F_"):
                t = int(cid[2:], 16)
            elif cid.startswith("LIBRARY@"):
                t = int(cid[8:], 16) + MZ_HEADER_SIZE
            else:
                continue
            if (t >= lib_lo or t < C0S_END) and e["site_file_offset"] < lib_lo:
                lib_edges.append((e["site_file_offset"], t))
        self.census_edges_total = len(lib_edges)
        self.census_edges_found = sum(1 for e in lib_edges if e in mine)
        self.census_edges_missing = [(hex(a), hex(b)) for a, b in lib_edges if (a, b) not in mine]
        self.addr_taken_raw = addr_taken


def extra_checks(A: Analysis):
    """Everything that is not a per-module match: padding, _INIT_ table, floats, other libs, roots."""
    lib_lo, lib_hi = A.text_place[0]["start"], A.text_place[-1]["end"]
    # -- segment-tail padding of the code area and of the INITDATA/EXITDATA area
    nxt = MZ_HEADER_SIZE + align_up(lib_hi - MZ_HEADER_SIZE, 16)
    A.tail_pad = {"start": lib_hi, "end": nxt, "size": nxt - lib_hi,
                  "all_zero": not any(A.data[lib_hi:nxt]),
                  "reason": "next segment (FAR_DATA class, C0S _FARDATA is paragraph-aligned) starts at "
                            f"{nxt:#x}; reloc value {(nxt - MZ_HEADER_SIZE) // 16:#x}"}
    A.init_pad = {"start": A.init_end, "end": A.ds_base, "size": A.ds_base - A.init_end,
                  "all_zero": not any(A.data[A.init_end:A.ds_base]),
                  "reason": "C0S _DATA is paragraph-aligned; _EXIT_/_EXITEND_ contribute no bytes"}
    # -- _INIT_ table entries
    entries = []
    for p in A.init_place:
        raw = A.data[p["start"]:p["end"]]
        calltype, prio, off = raw[0], raw[1], struct.unpack_from("<H", raw, 2)[0]
        tgt = off + MZ_HEADER_SIZE
        tm = next((q for q in A.text_place if q["start"] == tgt), None)
        entries.append({"module": p["module"], "file_start": p["start"], "calltype": calltype,
                        "priority": prio, "target_file_offset": tgt,
                        "target": [n for n, _ in A.names.get(tgt, [])] or
                                  ([f"{tm['module']}+0x0 (start of module _TEXT; its public "
                                    f"__{tm['module'].lower()}__ is an absolute link marker)"] if tm else [])})
    A.init_entries = entries
    # -- who calls what in the game
    A.game_roots = sorted({r["module"] for r in A.call_res if r["region"] == "CS.LIB" and r["module"]}
                          | {t["module"] for t in
                             [{"module": A.names[a["target"]][0][1]} for a in A.addr_taken_raw]},
                          key=lambda n: A.index[n])
    explained = set(A.game_roots) | A.c0s_pulled
    A.roots_unexplained = [n for n in A.roots if n not in explained]
    # -- floating point: any x87-emulator interrupt (INT 34h..3Dh) in the swept game code?
    emu = [hex(s) for s in sorted(A.insn_starts)
           if A.data[s] == 0xCD and 0x34 <= A.data[s + 1] <= 0x3D]
    A.float_check = {"emulator_int_34_3d_instructions_in_game_code": len(emu), "sites": emu[:20],
                     "float_externs_in_linked_modules": sorted(
                         {e for n in A.linked for e in A.by_name[n].externs
                          if e in ("FIDRQQ", "FIWRQQ", "FIERQQ", "FJARQQ", "FJCRQQ", "__turboFloat", "__REALCVT",
                                   "__scantod", "__realcvt")})}
    # -- is any module of the other runtime libraries present (MATHS etc.)?
    other = {}
    for libname in ("MATHS.LIB", "OLDSTRMS.LIB"):
        path = LIB_DIR / libname
        if not path.exists():
            continue
        hits = []
        for m in load_library(path):
            si = m.seg_by_name("_TEXT") if not m.parse_error else None
            if si is None or not m.segs[si].length:
                continue
            h = find_masked(A.data, m.segs[si], masked_positions(m, si), C0S_END, A.tail_pad["end"])
            if h:
                hits.append({"module": m.name, "offsets": [hex(x) for x in h]})
        other[libname] = hits
    A.other_libs = other
    # -- game code vs library boundary evidence
    A.boundary = {"first_library_byte": lib_lo,
                  "last_game_byte_value": A.data[lib_lo - 1],
                  "text_hits_below_boundary_in_game_range": [
                      (n, hex(h)) for n, hs in A.text_hits.items() for h in hs if h < lib_lo]}


def first_scanner_gap_analysis(A: Analysis):
    """Why tools/library_scanner.py (census-size anchor + literal memmem) missed each module."""
    manifest = json.loads(MANIFEST_PATH.read_text())
    old = {r["library_module"].split(":", 1)[1] for r in manifest["regions"]
           if r["kind"] == "KNOWN_LIBRARY" and r["library_module"].startswith("CS.LIB:")}
    census = {f["start"]: f for f in json.loads(CENSUS_PATH.read_text())["functions"]}
    out = []
    for p in A.text_place:
        n = p["module"]
        if n in old:
            continue
        m = A.by_name[n]
        si = m.seg_by_name("_TEXT")
        nmask = len(masked_positions(m, si))
        c = census.get(p["start"])
        why = []
        if c is None:
            why.append("no call-graph-census function starts here")
        elif c["size"] != p["size"]:
            why.append(f"census function {c['id']} is {c['size']} bytes, module _TEXT is {p['size']}")
        if nmask:
            why.append(f"{nmask} fixup bytes differ from the object's placeholders, so the literal-memmem fallback cannot match")
        if p["size"] < 16:
            why.append("under the memmem minimum size")
        if p["pad_before"]:
            why.append(f"{p['pad_before']} bytes of segment-alignment padding precede it")
        out.append(OrderedDict([("module", n), ("size", p["size"]), ("reasons", why)]))
    for n in A.dbss_only:
        out.append(OrderedDict([("module", n), ("size", 0),
                                ("reasons", ["no _TEXT segment at all: a _TEXT-only scanner cannot see it"])]))
    return out


def census_library_functions(A: Analysis):
    """Label every call-graph-census function that lies in the library area."""
    lib_lo = A.text_place[0]["start"]
    census = json.loads(CENSUS_PATH.read_text())["functions"]
    out = []
    for f in sorted(census, key=lambda f: f["start"]):
        if f["start"] < lib_lo:
            continue
        mod = next((p for p in A.text_place if p["start"] <= f["start"] < p["end"]), None)
        rec = {"id": f["id"], "start": f["start"], "size": f["size"]}
        if mod is None:
            rec["module"] = None
        else:
            rec["module"] = mod["module"]
            rec["offset_in_module"] = f["start"] - mod["start"]
            names = A.names.get(f["start"])
            rec["symbol"] = names[0][0] if names else None
            rec["label"] = rec["symbol"] or f"{mod['module']}+0x{rec['offset_in_module']:x}"
        out.append(rec)
    return out


def build_call_map(A: Analysis):
    census = {f["start"]: f for f in json.loads(CENSUS_PATH.read_text())["functions"]}
    by_fn = defaultdict(list)
    for r in sorted(A.call_res, key=lambda r: r["site"]):
        by_fn[r["caller_start"]].append(r)
    fns = OrderedDict()
    for start in sorted(by_fn):
        rows = by_fn[start]
        f = census.get(start)
        counts = defaultdict(int)
        for r in rows:
            counts[r["symbols"][0]] += 1
        fns[f"F_{start:04X}"] = OrderedDict([
            ("start", start), ("in_census", f is not None),
            ("census_id", f["id"] if f else None),
            ("library_calls", dict(sorted(counts.items()))),
            ("sites", [OrderedDict([("site", r["site"]), ("op", r["op"]), ("target", r["target"]),
                                    ("symbol", r["symbols"][0]), ("c_name", c_name(r["symbols"][0])),
                                    ("module", r["module"])]) for r in rows]),
        ])
    lib = OrderedDict()
    for r in sorted(A.call_res, key=lambda r: (r["target"], r["site"])):
        e = lib.setdefault(f"{r['target']:#06x}", OrderedDict([
            ("address", r["target"]), ("symbol", r["symbols"][0]), ("c_name", c_name(r["symbols"][0])),
            ("aliases", r["symbols"][1:]), ("module", r["module"]), ("callers", []), ("call_sites", 0)]))
        cid = f"F_{r['caller_start']:04X}"
        if cid not in e["callers"]:
            e["callers"].append(cid)
        e["call_sites"] += 1
    return fns, lib


def build_report(A: Analysis):
    lib_lo = A.text_place[0]["start"]
    lib_hi = A.text_place[-1]["end"]
    manifest = json.loads(MANIFEST_PATH.read_text())
    known_before = sum(r["end"] - r["start"] for r in manifest["regions"]
                       if r["kind"] == "KNOWN_LIBRARY" and r["library_module"].startswith("CS.LIB:"))
    module_bytes = sum(p["size"] for p in A.text_place)
    pad_bytes = sum(p["pad_before"] for p in A.text_place)

    def fx_brief(fr):
        d = {k: fr[k] for k in ("total", "verified", "inferred", "mismatch", "unverified")}
        d["verified_by_kind"] = fr["verified_by_kind"]
        d["unverified_reasons"] = fr["unverified_reasons"]
        d["mismatches"] = fr["mismatches"]
        return d

    def pulled(n):
        why = []
        if n in A.c0s_pulled:
            why.append("C0S extern")
        if n in A.game_roots:
            why.append("game call site")
        for w in sorted(A.pulled_by.get(n, set()), key=lambda x: A.index.get(x, -1)):
            if w != "C0S":
                why.append("module " + w)
        return why

    modules = []
    for p in A.text_place:
        n = p["module"]
        m = A.by_name[n]
        bv = A.byte_verify[n]
        entry = OrderedDict()
        entry["module"] = n
        entry["library_index"] = A.index[n]
        entry["kind"] = "KNOWN_LIBRARY"
        entry["publics"] = [OrderedDict([("symbol", pub["name"]), ("address", p["start"] + pub["offset"])])
                            for pub in m.publics
                            if pub["seg"] is not None and m.segs[pub["seg"]].name == "_TEXT"]
        t = bv["_TEXT"]
        entry["start"], entry["end"], entry["size"] = p["start"], p["end"], p["size"]
        entry["cs_offset"] = p["start"] - MZ_HEADER_SIZE
        entry["alignment_padding_before"] = p["pad_before"]
        entry["segment_align_bytes"] = p["align"]
        entry["matched_nonfixup_bytes"] = t["exact_nonfixup_bytes"]
        entry["fixup_masked_bytes"] = t["fixup_masked_bytes"]
        entry["undefined_bytes"] = t["undefined_bytes"]
        entry["unexplained_diffs"] = t["unexplained_diffs"]
        for seg in ("_DATA", "_INIT_"):
            if seg in bv:
                entry[seg.strip("_").lower()] = bv[seg]
        bs = m.seg_len("_BSS")
        if bs:
            entry["bss"] = {"size": bs, "ds_offset": (A.bss_file[n] - A.ds_base) if n in A.bss_file else None}
        entry["fixups"] = fx_brief(A.fixup_report[n])
        entry["identified"] = all(v["unexplained_diffs"] == 0 and v["undefined_bytes_nonzero_in_image"] == 0
                                  for v in bv.values()) and A.fixup_report[n]["mismatch"] == 0
        entry["why_linked"] = pulled(n)
        entry["module_sha256"] = m.blob_sha256
        modules.append(entry)

    data_only = []
    for n in A.dbss_only:
        m = A.by_name[n]
        bv = A.byte_verify.get(n, {})
        entry = OrderedDict()
        entry["module"] = n
        entry["library_index"] = A.index[n]
        entry["kind"] = "KNOWN_LIBRARY"
        entry["publics"] = [OrderedDict([("symbol", pub["name"]),
                                         ("segment", m.segs[pub["seg"]].name if pub["seg"] is not None else "ABS"),
                                         ("ds_offset", (A.data_base(n) - A.ds_base + pub["offset"])
                                          if pub["seg"] is not None and m.segs[pub["seg"]].name == "_DATA" else None)])
                            for pub in m.publics]
        d = bv.get("_DATA")
        entry["data"] = d
        entry["ds_start"] = (d["start"] - A.ds_base) if d else None
        entry["ds_end"] = (d["end"] - A.ds_base) if d else None
        entry["identified"] = bool(bv) and all(v["unexplained_diffs"] == 0 for v in bv.values())
        entry["fixups"] = fx_brief(A.fixup_report[n])
        entry["why_linked"] = pulled(n)
        entry["module_sha256"] = m.blob_sha256
        data_only.append(entry)

    c0s_d = A.c0s.seg_len("_DATA")
    lib0 = A.lib_data_start
    dg = [OrderedDict([("owner", "C0S.OBJ"), ("segment", "_DATA"), ("ds_start", 0), ("ds_end", c0s_d),
                       ("file_start", A.ds_base), ("file_end", A.ds_base + c0s_d)]),
          OrderedDict([("owner", "GAME objects"), ("segment", "_DATA"), ("ds_start", c0s_d),
                       ("ds_end", lib0 - A.ds_base), ("file_start", A.ds_base + c0s_d), ("file_end", lib0),
                       ("note", "everything between the end of C0S _DATA and the first library _DATA contribution")])]
    for p in A.data_place:
        m = A.by_name[p["module"]]
        if p["pad_before"]:
            dg.append(OrderedDict([("owner", "alignment padding"), ("segment", "_DATA"),
                                   ("ds_start", p["start"] - p["pad_before"] - A.ds_base),
                                   ("ds_end", p["start"] - A.ds_base),
                                   ("file_start", p["start"] - p["pad_before"]), ("file_end", p["start"])]))
        dg.append(OrderedDict([
            ("owner", "CS.LIB:" + p["module"]), ("segment", "_DATA"),
            ("ds_start", p["start"] - A.ds_base), ("ds_end", p["end"] - A.ds_base),
            ("file_start", p["start"]), ("file_end", p["end"]),
            ("publics", [OrderedDict([("symbol", pub["name"]),
                                      ("ds_offset", p["start"] - A.ds_base + pub["offset"])])
                         for pub in m.publics
                         if pub["seg"] is not None and m.segs[pub["seg"]].name == "_DATA"])]))
    bss = []
    for b in A.bss_chain:
        bss.append(b)
    report = OrderedDict()
    report["schema"] = "dave-library-map-v1"
    report["generator"] = "tools/library_scanner2.py"
    report["library"] = OrderedDict([("file", "toolchain/LIB/CS.LIB"), ("sha256", A.lib_sha),
                                     ("startup", "toolchain/LIB/C0S.OBJ"),
                                     ("startup_sha256", A.c0s.blob_sha256), ("member_count", len(A.mods))])
    report["coordinates"] = OrderedDict([
        ("file_offset_minus_cs_offset", MZ_HEADER_SIZE), ("dgroup_paragraph", A.dgroup_para),
        ("ds_base_file_offset", A.ds_base), ("ds_offset_to_file_offset", f"file = {A.ds_base:#x} + ds_offset")])
    report["summary"] = OrderedDict([
        ("c0s_text", OrderedDict([("start", MZ_HEADER_SIZE), ("end", C0S_END), ("size", C0S_END - MZ_HEADER_SIZE)])),
        ("game_code", OrderedDict([("start", C0S_END), ("end", lib_lo), ("size", lib_lo - C0S_END)])),
        ("library_text", OrderedDict([("start", lib_lo), ("end", lib_hi), ("size", lib_hi - lib_lo),
                                      ("module_bytes", module_bytes), ("alignment_padding_bytes", pad_bytes),
                                      ("module_count", len(A.text_place))])),
        ("tail_padding_after_text", A.tail_pad),
        ("library_text_unidentified_bytes", 0 if not A.tile_problems else None),
        ("tile_problems", A.tile_problems),
        ("manifest_known_cs_lib_text_bytes_before", known_before),
        ("identified_cs_lib_text_bytes_after", module_bytes),
        ("data_only_modules", A.dbss_only),
        ("unresolved_externs", A.unresolved_externs),
        ("notes", A.notes),
    ])
    report["boundary_evidence"] = A.boundary
    report["link_order"] = [p["module"] for p in A.text_place]
    report["link_order_full"] = [n for n in sorted(A.linked, key=lambda n: A.index[n])]
    report["modules"] = modules
    report["data_only_modules"] = data_only
    report["padding"] = A.pads + [dict(where="after last library _TEXT", **A.tail_pad),
                                  dict(where="between _INIT_ table and DGROUP", **A.init_pad)]
    report["dgroup"] = OrderedDict([
        ("ds_base_file_offset", A.ds_base),
        ("initialised_image_size", len(A.data) - A.ds_base),
        ("segments", dg),
        ("game_data_range", OrderedDict([("file_start", A.ds_base + c0s_d), ("file_end", lib0),
                                         ("ds_start", c0s_d), ("ds_end", lib0 - A.ds_base)])),
        ("library_data_range", OrderedDict([("file_start", lib0), ("file_end", len(A.data)),
                                            ("ds_start", lib0 - A.ds_base), ("ds_end", len(A.data) - A.ds_base)])),
        ("init_table", OrderedDict([("file_start", A.init_base), ("file_end", A.init_end),
                                    ("igroup_egroup_paragraph", (A.init_base - MZ_HEADER_SIZE) // 16),
                                    ("entries", A.init_entries), ("padding", A.init_pad),
                                    ("note", "C0S _INIT_/_EXIT_ contribute 0 bytes; entries come from SETUPIO and SETENVP")])),
        ("bss", OrderedDict([
            ("library_contributions", bss), ("chain_consistent", A.bss_chain_ok),
            ("library_bss_start_ds_offset", A.bss_chain[0]["dgroup_offset"]),
            ("library_bss_end_ds_offset", A.bss_end_file - A.ds_base),
            ("game_bss_inferred", OrderedDict([
                ("ds_start", (A.game_bss_start_file - A.ds_base) if A.game_bss_start_file else None),
                ("note", "start of all BSS, from C0S's own fixups; initialised image ends at DS "
                         f"{len(A.data) - A.ds_base:#x}")]))])),
        ("not_in_file_but_referenced_by_c0s", ["_CVTSEG", "_SCNSEG", "_BSSEND", "_STACK"]),
    ])
    report["c0s_segments_accounted"] = OrderedDict([
        ("_TEXT", [MZ_HEADER_SIZE, C0S_END]),
        ("_DATA", [A.ds_base, A.ds_base + c0s_d]),
        ("_INIT_/_INITEND_", "0 bytes by C0S; entries contributed by SETUPIO and SETENVP at "
                             f"[{A.init_base:#x},{A.init_end:#x}), group paragraph {(A.init_base - MZ_HEADER_SIZE) // 16:#x} "
                             "(the segment referenced twice by C0S reloc entries at CS:0xDE and CS:0x110)"),
        ("_EXIT_/_EXITEND_", "0 bytes (no linked module registers an exit-time entry)"),
        ("_OVERLAY_/_1STUB_/_FARDATA", "0 bytes in C0S"),
        ("_CVTSEG/_SCNSEG", "0 bytes (CVTFAK not linked; no printf %f/scanf %f support)"),
    ])
    report["why_linked"] = OrderedDict([
        ("roots_not_pulled_by_any_other_linked_module", A.roots),
        ("roots_unexplained_by_c0s_or_game_call_sites", A.roots_unexplained),
        ("c0s_extern_providers", sorted(A.c0s_pulled, key=lambda n: A.index[n])),
        ("modules_called_directly_by_game_code", A.game_roots),
        ("ordering_rule",
         "TLINK emits the CS.LIB members it pulls in library-member order, not in dependency or "
         "discovery order. CS.LIB's members come in three alphabetical runs (0-146, 147-257, 285-311, "
         "with the C++ stream members 258-284 in between); the observed order is strictly increasing in "
         "member index across all runs."),
    ])
    report["checks"] = OrderedDict([
        ("floating_point", A.float_check),
        ("other_runtime_libraries_found_in_image", A.other_libs),
        ("fixup_totals", A.fixup_totals),
        ("call_site_cross_check", OrderedDict([
            ("census_call_edges_into_library_or_c0s", A.census_edges_total),
            ("reproduced_by_sweep", A.census_edges_found),
            ("missing", A.census_edges_missing),
            ("sweep_sites_with_unnamed_target", len(A.call_unnamed)),
            ("e8_candidates_not_decoded_as_instructions", len(A.undecoded_candidates))])),
    ])
    report["fixup_summary"] = OrderedDict((k, fx_brief(v)) for k, v in A.fixup_report.items())
    report["library_symbols"] = sorted(
        (OrderedDict([("address", a), ("cs_offset", a - MZ_HEADER_SIZE), ("symbol", ns[0][0]),
                      ("c_name", c_name(ns[0][0])), ("module", ns[0][1]), ("aliases", [n for n, _ in ns[1:]])])
         for a, ns in A.names.items()), key=lambda d: d["address"])
    report["census_library_functions"] = census_library_functions(A)
    report["first_scanner_gap_analysis"] = first_scanner_gap_analysis(A)
    fns, lib = build_call_map(A)
    report["call_sites"] = OrderedDict([("by_game_function", fns), ("by_library_function", lib),
                                        ("address_taken", [OrderedDict(site=a["site"], target=a["target"],
                                                                        symbol=A.names[a["target"]][0][0])
                                                           for a in A.addr_taken_raw])])
    return report


def render_markdown(R) -> str:
    S = R["summary"]
    L = []
    w = L.append
    w("# Library map (CS.LIB / C0S)")
    w("")
    w("Generated by `tools/library_scanner2.py` from `build/DAVE_unpacked.exe` against "
      f"`toolchain/LIB/CS.LIB` (sha256 `{R['library']['sha256'][:16]}...`) and `C0S.OBJ`. "
      "Machine-readable twin: `docs/library-map.json`. Coordinates: `file = CS offset + 0x200`; "
      f"`file = {R['coordinates']['ds_base_file_offset']:#x} + DS offset`.")
    w("")
    w("## Totals")
    w("")
    w(f"- C0S startup `_TEXT`: file [{S['c0s_text']['start']:#x},{S['c0s_text']['end']:#x}) ({S['c0s_text']['size']} bytes).")
    w(f"- **Game code: file [{S['game_code']['start']:#x},{S['game_code']['end']:#x}) = {S['game_code']['size']} bytes.** "
      f"`{S['game_code']['end']:#x}` is the first library byte (`ATEXIT`); no parseable CS.LIB, MATHS or OLDSTRMS "
      "module matches anywhere below it (the C++ stream members that tools/omf-style parsing cannot read are "
      "irrelevant: the library area tiles completely without them, and the game uses no C++ runtime). "
      "The last game bytes are hand-written asm (F_95D1: EGA port writes, `mov ax,254Dh; mov ds,ax; ret`).")
    lt = S["library_text"]
    w(f"- **Library `_TEXT`: file [{lt['start']:#x},{lt['end']:#x}) = {lt['size']} bytes**: "
      f"{lt['module_count']} CS.LIB modules = {lt['module_bytes']} bytes of module code + "
      f"{lt['alignment_padding_bytes']} zero bytes of SEGDEF-alignment padding (FARHEAP, NEARHEAP are paragraph-aligned).")
    tp = S["tail_padding_after_text"]
    w(f"- After `STACK` ends ({lt['end']:#x}) there are {tp['size']} zero bytes of paragraph padding up to {tp['end']:#x}, "
      "where the first far-data segment begins.")
    w(f"- Unidentified bytes inside the library `_TEXT` area: **{S['library_text_unidentified_bytes']}**.")
    w(f"- Library bytes recognised in the manifest before this tool: {S['manifest_known_cs_lib_text_bytes_before']} "
      f"(42 modules); after: {S['identified_cs_lib_text_bytes_after']} module bytes "
      f"(+{lt['alignment_padding_bytes']} padding).")
    ft = R["checks"]["fixup_totals"]
    w(f"- Fixups re-derived from the layout: {ft['total']} total, {ft['verified']} verified, "
      f"{ft['inferred']} inferred (BSS bases solved from the fixups themselves, cross-checked for chain consistency), "
      f"{ft['mismatch']} mismatches, {ft['unverified']} unverified.")
    fp = R["checks"]["floating_point"]
    w(f"- Floating point: {fp['emulator_int_34_3d_instructions_in_game_code']} x87-emulator interrupts in game code, "
      f"float externs in linked modules: {fp['float_externs_in_linked_modules'] or 'none'}. "
      "No emulator, MATHS or printf/scanf code is linked.")
    w("")
    w("## Link order")
    w("")
    w("TLINK emits the pulled CS.LIB members in **library-member order** (three alphabetical runs; "
      "member index strictly increases). Each module is linked because a previously linked module, `C0S`, "
      "or game code references one of its publics; the transitive extern closure of `C0S` + the 59 `_TEXT` "
      "modules reproduces exactly the 65-module set (59 with code + 6 data-only), with no unresolved extern "
      "except `_main`.")
    w("")
    w("| # | module | lib idx | file range | size | pad | non-fixup bytes matched | fixups ok/total | linked because |")
    w("|---|---|---|---|---|---|---|---|---|")
    for i, m in enumerate(R["modules"], 1):
        fx = m["fixups"]
        w(f"| {i} | {m['module']} | {m['library_index']} | {m['start']:#x}-{m['end']:#x} | {m['size']} | "
          f"{m['alignment_padding_before'] or ''} | {m['matched_nonfixup_bytes']} | "
          f"{fx['verified'] + fx['inferred']}/{fx['total']} | {', '.join(m['why_linked'])} |")
    w("")
    w("### Data-only modules (no `_TEXT`)")
    w("")
    w("| module | lib idx | DS range | publics | linked because |")
    w("|---|---|---|---|---|")
    for m in R["data_only_modules"]:
        pubs = ", ".join(f"{p['symbol']}@{p['ds_offset']:#x}" if p["ds_offset"] is not None else p["symbol"]
                         for p in m["publics"])
        w(f"| {m['module']} | {m['library_index']} | {m['ds_start']:#x}-{m['ds_end']:#x} | {pubs} | {', '.join(m['why_linked'])} |")
    w("")
    ru = R["why_linked"]
    w("Roots (pulled by no other linked module): " + ", ".join(ru["roots_not_pulled_by_any_other_linked_module"]) +
      f". Unexplained roots: {ru['roots_unexplained_by_c0s_or_game_call_sites'] or 'none'} "
      "(every root is called from game code or referenced by C0S).")
    w("")
    w("## DGROUP (DS) map")
    w("")
    dg = R["dgroup"]
    w(f"DS:0 = file {dg['ds_base_file_offset']:#x}; initialised image {dg['initialised_image_size']:#x} bytes.")
    w("")
    w("| DS range | file range | owner |")
    w("|---|---|---|")
    for s in dg["segments"]:
        pubs = ""
        if s.get("publics"):
            pubs = " (" + ", ".join(f"{p['symbol']}@{p['ds_offset']:#x}" for p in s["publics"]) + ")"
        w(f"| {s['ds_start']:#x}-{s['ds_end']:#x} | {s['file_start']:#x}-{s['file_end']:#x} | {s['owner']} {s['segment']}{pubs} |")
    w("")
    it = dg["init_table"]
    w(f"`_INIT_` table (paragraph {it['igroup_egroup_paragraph']:#x}, the segment referenced twice by C0S): "
      f"file [{it['file_start']:#x},{it['file_end']:#x}) then {it['padding']['size']} zero pad bytes to DGROUP. Entries: " +
      "; ".join(f"{e['module']}: priority {e['priority']} -> {', '.join(e['target'])}" for e in it["entries"]) + ".")
    b = dg["bss"]
    gb = b["game_bss_inferred"]["ds_start"]
    w("")
    w(f"BSS (not in the file): game BSS starts at about DS {gb:#x}; library BSS "
      f"DS [{b['library_bss_start_ds_offset']:#x},{b['library_bss_end_ds_offset']:#x}): " +
      ", ".join(f"{c['module']}@{c['dgroup_offset']:#x}({c['size']})" for c in b["library_contributions"]) + ".")
    w("")
    w("## Library function addresses (call-site names)")
    w("")
    w("| file addr | CS offset | symbol | module | game call sites |")
    w("|---|---|---|---|---|")
    called = R["call_sites"]["by_library_function"]
    for s in R["library_symbols"]:
        if s["module"] == "C0S":
            continue
        c = called.get(f"{s['address']:#06x}")
        w(f"| {s['address']:#x} | {s['cs_offset']:#x} | `{s['symbol']}` | {s['module']} | "
          f"{c['call_sites'] if c else ''} |")
    w("")
    w("## Game function -> library calls")
    w("")
    w("Every near CALL/JMP in the game range whose target is a library entry (linear sweep of every census "
      "function and every `55 8B EC` prologue; reproduces all of the call-graph census's library edges).")
    w("")
    w("| game function | library calls |")
    w("|---|---|")
    for fid, f in R["call_sites"]["by_game_function"].items():
        calls = ", ".join(f"{k} x{v}" if v > 1 else k for k, v in f["library_calls"].items())
        flag = "" if f["in_census"] else " (not in census)"
        w(f"| {fid}{flag} | {calls} |")
    w("")
    c = R["checks"]["call_site_cross_check"]
    w(f"Cross-check: census call edges into library/C0S {c['census_call_edges_into_library_or_c0s']}, "
      f"reproduced {c['reproduced_by_sweep']}; sites with unnamed target: {c['sweep_sites_with_unnamed_target']}.")
    w("")
    w("## Method notes / why the first scanner missed these")
    w("")
    w("Modules the first scanner could not place, and why (new this run: %d):" % len(R["first_scanner_gap_analysis"]))
    w("")
    w("| module | _TEXT | reasons |")
    w("|---|---|---|")
    for g in R["first_scanner_gap_analysis"]:
        w(f"| {g['module']} | {g['size'] or '-'} | {'; '.join(g['reasons'])} |")
    w("")
    w("- FARHEAP and NEARHEAP are paragraph-aligned SEGDEFs: 10 and 15 zero bytes before them are linker padding, "
      "not unknown code.")
    w("- FILES/FILES2/CTYPE/FMODE/HEAPLEN/STKLEN contribute only `_DATA`, so a `_TEXT`-only scanner cannot see them; "
      "they are found by the extern closure and confirmed by byte-comparing the `_DATA` tail of the image.")
    w("- This scan uses masked search keyed on each module's longest unmasked run, requires the hits to tile one "
      "contiguous run in library order, then evaluates the fixups instead of merely masking them.")
    w("")
    return "\n".join(L) + "\n"


def run_all():
    A = Analysis()
    A.search_text()
    A.tile()
    A.closure()
    A.layout_data()
    A.infer_bss()
    A.verify_fixups()
    A.verify_bytes()
    A.padding()
    A.name_table()
    A.call_sites()
    extra_checks(A)
    A.fixup_totals = {"total": 0, "verified": 0, "inferred": 0, "mismatch": 0, "unverified": 0}
    for v in A.fixup_report.values():
        for k in A.fixup_totals:
            A.fixup_totals[k] += v[k]
    return A


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write docs/library-map.json and docs/library-map.md")
    args = ap.parse_args()
    A = run_all()
    R = build_report(A)
    S = R["summary"]
    print(f"game code      : [{S['game_code']['start']:#x},{S['game_code']['end']:#x}) {S['game_code']['size']} bytes")
    lt = S["library_text"]
    print(f"library _TEXT  : [{lt['start']:#x},{lt['end']:#x}) {lt['size']} bytes = {lt['module_bytes']} module + "
          f"{lt['alignment_padding_bytes']} padding, {lt['module_count']} modules")
    print(f"data-only mods : {A.dbss_only}")
    print(f"fixups         : {A.fixup_totals}")
    print(f"tile problems  : {A.tile_problems}   unresolved externs: {A.unresolved_externs}")
    print(f"roots unexplained: {A.roots_unexplained}   notes: {A.notes}")
    bad = [m["module"] for m in R["modules"] + R["data_only_modules"] if not m["identified"]]
    print(f"modules not fully identified: {bad}")
    if args.write:
        (ROOT / "docs" / "library-map.json").write_text(json.dumps(R, indent=2) + "\n")
        (ROOT / "docs" / "library-map.md").write_text(render_markdown(R))
        print("wrote docs/library-map.json and docs/library-map.md")
    return 0 if not bad and not A.tile_problems and A.fixup_totals["mismatch"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
