"""Strict compile-and-compare for promoting MATCHING_C regions.

Pipeline: compile candidate.c with the pinned Turbo C++ 1.00 toolchain
(tools/compile_probe.py) -> parse the OMF object (tools/omf.py) -> place its
_TEXT at the original CS address -> RESOLVE EVERY FIXUP the way TLINK would,
using the symbol map (tools/symbols.py) and the candidate's segment
placements -> compare the fully linked bytes with build/DAVE_unpacked.exe.

Nothing is masked. A fixup is a claim ("this operand is the address of X");
the matcher computes X's address independently and the resulting bytes must
equal the original. Verdicts:

  EXACT              every byte of the extent equals the original after
                     resolving every fixup; every base16 fixup sits on a real
                     MZ relocation entry with the expected paragraph.
  UNRESOLVED_FIXUPS  all non-fixup bytes equal, but some fixups name symbols
                     or segments with no known address (reported by name).
                     Not promotable.
  MISMATCH           at least one byte differs (listed with disassembly
                     context). Not promotable.

Placement:
* `_TEXT` is placed so every public function lands on its symbol-map address
  (named in layout/symbols.json, or a placeholder `F_XXXX` = census id /
  file offset). All publics must agree on one base. `--at` overrides.
* A candidate's own `_DATA`/`_BSS` (string literals, statics, globals it
  defines) need a DS base: give it in the source as a directive comment
      /* @seg _DATA 0x07c8 */   /* @seg _BSS 0x9ec0 */
  When a `_DATA` base is given, the candidate's `_DATA` bytes are ALSO
  compared with the original DGROUP bytes there (verifies string literals and
  initialisers).

Usage:
    python tools/match_function.py src/foo.c [--at 0x6b64] [--flags "..."] [--json]
        [--apply --id F_6D64 --description "..."]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys

import capstone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_probe  # noqa: E402
import tcc  # noqa: E402
import omf  # noqa: E402
import reconstruct  # noqa: E402
from symbols import SymbolMap, HDR, DGROUP_PARA, TEXT_PARA  # noqa: E402

MANIFEST_PATH = ROOT / "layout" / "manifest.json"
UNPACKED_PATH = ROOT / "build" / "DAVE_unpacked.exe"
DGROUP_FILE = HDR + DGROUP_PARA * 16

_md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def unpacked_bytes() -> bytes:
    data = UNPACKED_PATH.read_bytes()
    expected = load_manifest()["unpacked_original"]
    if len(data) != expected["size"] or hashlib.md5(data).hexdigest() != expected["md5"]:
        raise SystemExit("build/DAVE_unpacked.exe does not match the pinned specimen")
    return data


def relocation_sites(image: bytes) -> set:
    h = struct.unpack_from("<14H", image, 0)
    sites = set()
    for i in range(h[3]):
        off, seg = struct.unpack_from("<HH", image, h[12] + 4 * i)
        sites.add(seg * 16 + off)
    return sites


def parse_directives(source_text: str) -> dict:
    segs = {}
    for name, value in re.findall(r"@seg\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)", source_text):
        if name in segs and segs[name] != int(value, 0):
            raise SystemExit(f"conflicting @seg {name} directives")
        segs[name] = int(value, 0)
    return segs


def parse_at(source_text: str):
    """`/* @at 0x0239 */`: the CS offset of the object's _TEXT (a whole
    translation unit names its functions meaningfully, so it cannot be placed
    by census-id publics)."""
    found = {int(v, 0) for v in re.findall(r"@at\s+(0x[0-9A-Fa-f]+|\d+)", source_text)}
    if len(found) > 1:
        raise SystemExit(f"conflicting @at directives: {sorted(found)}")
    return found.pop() if found else None


def object_symbols(mod, text_at: int, segs: dict) -> list:
    """[(name, kind, address)] of a placed object's PUBDEFs: _TEXT publics are
    code at text_at + offset, publics of a placed DGROUP segment are data at
    its DS base + offset. These are what other objects' EXTDEFs resolve to."""
    out = []
    for pub in mod.publics:
        seg = pub["segment"]
        if seg == "_TEXT":
            out.append((pub["name"], "code", text_at + pub["offset"]))
        elif seg in segs:
            out.append((pub["name"], "data", segs[seg] + pub["offset"]))
        else:
            raise SystemExit(f"public {pub['name']} in unplaced segment {seg}")
    return out


def declared_segment(mod, name: str) -> bytes:
    """A segment's full image: LEDATA bytes padded with zeros to the SEGDEF
    length. TCC writes no data record for all-zero initialised data (e.g.
    `char buf[6] = "";`), so that data exists only as the declared length."""
    length = mod.segment_length(name) or 0
    data = bytes(mod.segments.get(name, b""))
    return data + b"\x00" * max(0, length - len(data))


def text_base(mod, symbols: SymbolMap, at: int | None):
    if at is not None:
        # an explicit placement must still agree with every public whose
        # address is already known (curated names such as _main, census ids)
        for pub in mod.publics:
            if pub["segment"] != "_TEXT":
                continue
            known = symbols.resolve_code(pub["name"])
            if known is not None and known != at + pub["offset"]:
                raise SystemExit(f"@at {at:#06x} puts {pub['name']} at {at + pub['offset']:#06x}, "
                                 f"but it is known at {known:#06x}")
        return at, []
    bases = []
    for pub in mod.publics:
        if pub["segment"] != "_TEXT":
            continue
        addr = symbols.resolve_code(pub["name"])
        if addr is not None:
            bases.append((pub["name"], addr - pub["offset"]))
    if not bases:
        raise SystemExit("cannot place _TEXT: no public function has a known address; use --at")
    distinct = {b for _, b in bases}
    if len(distinct) != 1:
        raise SystemExit(f"publics disagree on the _TEXT base: {bases}")
    return bases[0][1], bases


def link(mod, base: int, segs: dict, symbols: SymbolMap, image: bytes, seg_name: str = "_TEXT"):
    """Return (linked segment bytes, per-fixup report list).

    seg_name "_TEXT": `base` is the CS offset of the segment. A DGROUP segment
    (`_DATA`, e.g. pointer initialisers): `base` is its DS offset; its fixups
    are resolved the same way (no self-relative ones), and a base16 fixup
    must sit on an MZ relocation at its load-module offset."""
    if seg_name == "_TEXT":
        text = bytearray(mod.segment_bytes("_TEXT"))
        lm_base = TEXT_PARA * 16 + base
    else:
        text = bytearray(declared_segment(mod, seg_name))
        lm_base = DGROUP_PARA * 16 + base
    relocs = relocation_sites(image)
    report = []
    for fx in mod.fixups_in(seg_name):
        site = base + fx["offset"]           # offset of the patched bytes in its frame
        if seg_name != "_TEXT" and fx["self_relative"]:
            report.append({"offset": fx["offset"], "cs": site, "target": fx["target"],
                           "kind": fx["target_kind"], "status": "self-relative fixup in data"})
            continue
        entry = {"offset": fx["offset"], "cs": site, "loc": fx["loc"],
                 "target": fx["target"], "kind": fx["target_kind"],
                 "frame": fx.get("frame"), "self_relative": fx["self_relative"]}
        report.append(entry)

        # Resolve the target to (paragraph, offset-within-frame).
        para = off = None
        if fx["target_kind"] == "external":
            name = fx["target"]
            code = symbols.resolve_code(name)
            data = symbols.resolve_data(name)
            far = symbols.resolve_far(name)
            if code is not None:
                para, off = TEXT_PARA, code
            elif data is not None:
                para, off = DGROUP_PARA, data
            elif far is not None:
                para, off = far
        elif fx["target_kind"] == "segment":
            seg = fx["target"]
            if seg == "_TEXT":
                para, off = TEXT_PARA, base
            elif seg in segs:
                para, off = DGROUP_PARA, segs[seg]
        elif fx["target_kind"] == "group" and fx["target"] == "DGROUP":
            para, off = DGROUP_PARA, 0
        if para is None:
            entry["status"] = "unresolved"
            continue
        off += fx["displacement"]
        entry["resolved"] = {"para": para, "offset": off}

        loc, o = fx["loc"], fx["offset"]
        if loc in ("offset16", "loader-offset16"):
            cur = struct.unpack_from("<H", text, o)[0]
            if fx["self_relative"]:
                val = (cur + off - (site + 2)) & 0xFFFF
            else:
                val = (cur + off) & 0xFFFF
            struct.pack_into("<H", text, o, val)
        elif loc == "lobyte":
            cur = text[o]
            if fx["self_relative"]:
                text[o] = (cur + off - (site + 1)) & 0xFF
            else:
                text[o] = (cur + off) & 0xFF
        elif loc == "base16":
            struct.pack_into("<H", text, o, para)
            entry["mz_relocation"] = (lm_base + o) in relocs
        elif loc == "pointer32":
            cur = struct.unpack_from("<H", text, o)[0]
            struct.pack_into("<HH", text, o, (cur + off) & 0xFFFF, para)
            entry["mz_relocation"] = (lm_base + o + 2) in relocs
        else:
            entry["status"] = f"unsupported loc {loc}"
            continue
        entry["status"] = "resolved"
    return bytes(text), report


def context(cs: int, image: bytes, n: int = 24) -> list:
    lm = image[HDR:]
    out = []
    for i in _md.disasm(lm[max(0, cs - 4):cs + n], max(0, cs - 4)):
        out.append(f"{i.address:04x} {i.bytes.hex():12s} {i.mnemonic} {i.op_str}")
    return out


def run_match(source: pathlib.Path, flags: str = "", at: int | None = None, model: str = "s") -> dict:
    if model != "s":
        obj_path = compile_probe.run(source, model, flags)
    else:
        obj_path = tcc.compile_many([source], extra_flags=flags)[0]
        if obj_path is None:
            log = (ROOT / "build" / "tcc_batch" / "S0001.LOG")
            raise SystemExit("compile failed: " + (log.read_text(errors="replace") if log.exists() else ""))
    return match_object(obj_path.read_bytes(), source, at=at, flags=flags, model=model)


_IMAGE = None
_SYMBOLS = None


GAME_BSS = (0x4C60, 0x9EC8)       # docs/data-layout.md: C0S clears from 0x4C60; CS.LIB _BSS from 0x9EC8


def match_object(obj_bytes: bytes, source: pathlib.Path, at: int | None = None,
                 flags: str = "", model: str = "s", symbols: SymbolMap | None = None) -> dict:
    """Place, link and compare one object. `symbols` overrides the default
    symbol map (tools/verify_sources.py passes one extended with the publics
    of the other placed units and assembly modules)."""
    global _IMAGE, _SYMBOLS
    if _IMAGE is None:
        _IMAGE, _SYMBOLS = unpacked_bytes(), SymbolMap()
    image = _IMAGE
    symbols = symbols or _SYMBOLS
    text_src = source.read_text(encoding="latin1")
    segs = parse_directives(text_src)
    if at is None:
        at = parse_at(text_src)
    flags = (flags + " " + tcc.source_flags(text_src)).strip()
    mod = omf.OmfReader().read(obj_bytes, source.stem)
    base, bases = text_base(mod, symbols, at)
    linked, fixups = link(mod, base, segs, symbols, image)
    original = image[HDR + base:HDR + base + len(linked)]

    diffs = [i for i in range(len(linked)) if linked[i] != original[i]]
    unresolved = [f for f in fixups if f.get("status") != "resolved"]
    unresolved_bytes = set()
    for f in unresolved:
        unresolved_bytes.update(range(f["offset"], f["offset"] + 2))
    hard_diffs = [d for d in diffs if d not in unresolved_bytes]
    missing_reloc = [f for f in fixups if f.get("mz_relocation") is False]

    # Every non-empty segment other than _TEXT must be placed: its contents and
    # every reference into it are checked against that placement.
    unplaced = [n for n, length in mod.segment_lengths.items()
                if n != "_TEXT" and length and n not in segs]

    data_check = None
    cand = declared_segment(mod, "_DATA")
    if "_DATA" in segs and cand:
        dlinked, dfixups = link(mod, segs["_DATA"], segs, symbols, image, seg_name="_DATA")
        start = DGROUP_FILE + segs["_DATA"]
        orig = image[start:start + len(cand)]
        data_check = {"ds": segs["_DATA"], "length": len(cand),
                      "diffs": [i for i in range(len(cand)) if dlinked[i] != orig[i]],
                      "fixups": len(dfixups)}
        dbad = [f for f in dfixups if f.get("status") != "resolved"]
        if dbad:
            data_check["unresolved_fixups"] = [{"target": f["target"], "status": f.get("status")}
                                               for f in dbad]
        if any(f.get("mz_relocation") is False for f in dfixups):
            data_check["missing_mz_relocations"] = [f["cs"] for f in dfixups
                                                    if f.get("mz_relocation") is False]

    # _BSS: no bytes to compare (TLINK writes none). Every reference into it
    # was resolved above through the placed base; here the declared extent
    # must lie inside the game's _BSS and the base must be word aligned
    # (TCC's _BSS SEGDEF is WORD aligned).
    bss_check = None
    bss_len = mod.segment_length("_BSS") or 0
    if "_BSS" in segs and bss_len:
        b0 = segs["_BSS"]
        bss_check = {"ds": b0, "length": bss_len, "end": b0 + bss_len,
                     "inside_game_bss": GAME_BSS[0] <= b0 and b0 + bss_len <= GAME_BSS[1],
                     "aligned": b0 % 2 == 0,
                     "publics": sorted((p["offset"] + b0, p["name"]) for p in mod.publics
                                       if p["segment"] == "_BSS")}
    bss_bad = bool(bss_check) and not (bss_check["inside_game_bss"] and bss_check["aligned"])

    data_bad = bool(data_check) and bool(data_check["diffs"] or data_check.get("missing_mz_relocations"))
    if hard_diffs or missing_reloc or data_bad or bss_bad or unplaced:
        verdict = "MISMATCH"
    elif unresolved or (data_check and data_check.get("unresolved_fixups")):
        verdict = "UNRESOLVED_FIXUPS"
    else:
        verdict = "EXACT"

    return {
        "source": str(source).replace("\\", "/"),
        "verdict": verdict,
        "cs_start": base, "cs_end": base + len(linked),
        "file_start": HDR + base, "file_end": HDR + base + len(linked),
        "length": len(linked),
        "placement": bases,
        "segments": segs,
        "model": model, "flags": flags,
        "object_sha256": hashlib.sha256(obj_bytes).hexdigest(),
        "publics": mod.publics,
        "fixup_count": len(fixups),
        "unresolved_fixups": [{"target": f["target"], "kind": f["kind"], "cs": f["cs"],
                               "status": f.get("status")} for f in unresolved],
        "missing_mz_relocations": [f["cs"] for f in missing_reloc],
        "diffs": [{"offset": d, "cs": base + d, "got": linked[d], "want": original[d]}
                  for d in hard_diffs[:64]],
        "diff_count": len(hard_diffs),
        "first_diff_context": context(base + hard_diffs[0], image) if hard_diffs else [],
        "candidate_first_diff": (
            [f"{i.address:04x} {i.bytes.hex():12s} {i.mnemonic} {i.op_str}"
             for i in _md.disasm(linked[max(0, hard_diffs[0] - 4):hard_diffs[0] + 24],
                                 base + max(0, hard_diffs[0] - 4))]
            if hard_diffs else []),
        "data_check": data_check,
        "bss_check": bss_check,
        "unplaced_segments": unplaced,
        "fixups": fixups,
    }


def census_boundaries() -> set:
    census = json.loads((ROOT / "docs" / "function-census.json").read_text())
    b = set()
    for f in census["functions"]:
        b.add(f["cs_start"])
        b.add(f["cs_end"])
    return b


def apply_promotion(result: dict, region_id: str, description: str):
    if result["verdict"] != "EXACT":
        raise SystemExit(f"refusing to promote: verdict is {result['verdict']}")
    bounds = census_boundaries()
    if result["cs_start"] not in bounds or result["cs_end"] not in bounds:
        raise SystemExit("refusing to promote: extent does not coincide with census "
                         "function boundaries (docs/function-census.json)")
    manifest_backup = MANIFEST_PATH.read_text()
    raw_dir = ROOT / "raw"
    raw_backup = {p.name: p.read_bytes() for p in raw_dir.glob("*.bin")}

    manifest = load_manifest()
    regions = manifest["regions"]
    start, end = result["file_start"], result["file_end"]
    idx = next((i for i, r in enumerate(regions)
                if r["kind"] == "RAW_UNKNOWN" and r["start"] <= start and end <= r["end"]), None)
    if idx is None:
        raise SystemExit("target range is not inside a single RAW_UNKNOWN region")
    old = regions[idx]
    new = []
    if old["start"] < start:
        new.append({**old, "end": start, "id": f"RAW_{old['start']:X}_{start:X}",
                    "artifact": f"raw/RAW_{old['start']:X}_{start:X}.bin"})
    new.append({
        "id": region_id, "start": start, "end": end,
        "kind": "MATCHING_C", "classification": "code",
        "source": result["source"],
        "compile_flags": {"model": result["model"], "flags": result["flags"]},
        "object_sha256": result["object_sha256"],
        "description": description,
        "matching_status": "EXACT",
        "matching_status_note": (
            "tools/match_function.py (strict): every fixup resolved through the "
            "symbol map and placement; linked bytes equal the original over the "
            f"full extent [{start:#x},{end:#x}); {result['fixup_count']} fixups verified."),
        "artifact": f"raw/{region_id}.bin",
    })
    if end < old["end"]:
        new.append({**old, "start": end, "id": f"RAW_{end:X}_{old['end']:X}",
                    "artifact": f"raw/RAW_{end:X}_{old['end']:X}.bin"})
    regions[idx:idx + 1] = new
    manifest["regions"] = sorted(regions, key=lambda r: r["start"])
    reconstruct.validate_ownership(manifest)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    def restore():
        MANIFEST_PATH.write_text(manifest_backup)
        for p in raw_dir.glob("*.bin"):
            if p.name not in raw_backup:
                p.unlink()
        for name, content in raw_backup.items():
            (raw_dir / name).write_bytes(content)

    try:
        for tool in ("extract_raw.py", "reconstruct.py"):
            r = subprocess.run([sys.executable, str(ROOT / "tools" / tool)],
                               cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"{tool} failed:\n{r.stdout}\n{r.stderr}")
    except Exception:
        restore()
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=pathlib.Path)
    ap.add_argument("--at", default=None, help="CS offset to place _TEXT (default: from publics)")
    ap.add_argument("--model", default="s", choices=list(compile_probe.MODEL_FLAG))
    ap.add_argument("--flags", default="")
    ap.add_argument("--json", action="store_true", help="print the full JSON report")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--id", dest="region_id")
    ap.add_argument("--description")
    args = ap.parse_args()

    r = run_match(args.source, args.flags, int(args.at, 0) if args.at else None, args.model)
    if args.json:
        print(json.dumps({k: v for k, v in r.items()}, indent=1))
    else:
        print(f"{r['verdict']}: {r['source']} -> cs [{r['cs_start']:#06x},{r['cs_end']:#06x}) "
              f"file [{r['file_start']:#x},{r['file_end']:#x}) {r['length']} bytes, "
              f"{r['fixup_count']} fixups, {r['diff_count']} differing bytes")
        for u in r["unresolved_fixups"]:
            print(f"  unresolved: {u}")
        if r["missing_mz_relocations"]:
            print(f"  base16 fixups without MZ relocation at cs {r['missing_mz_relocations']}")
        if r["diffs"]:
            print("  first diffs:", ", ".join(f"+{d['offset']:#x} got {d['got']:02x} want {d['want']:02x}"
                                              for d in r["diffs"][:8]))
            print("  original:"); [print("    " + l) for l in r["first_diff_context"]]
            print("  candidate:"); [print("    " + l) for l in r["candidate_first_diff"]]
        if r["data_check"]:
            print(f"  _DATA check: {r['data_check']}")
    if args.apply:
        if not (args.region_id and args.description):
            raise SystemExit("--apply requires --id and --description")
        apply_promotion(r, args.region_id, args.description)
        print("applied")
    sys.exit(0 if r["verdict"] == "EXACT" else 1)


if __name__ == "__main__":
    main()
