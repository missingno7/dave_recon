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
        segs[name] = int(value, 0)
    return segs


def text_base(mod, symbols: SymbolMap, at: int | None):
    if at is not None:
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


def link(mod, base: int, segs: dict, symbols: SymbolMap, image: bytes):
    """Return (linked _TEXT bytes, per-fixup report list)."""
    text = bytearray(mod.segment_bytes("_TEXT"))
    relocs = relocation_sites(image)
    report = []
    for fx in mod.fixups_in("_TEXT"):
        site = base + fx["offset"]           # CS offset of the patched bytes
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
            if code is not None:
                para, off = TEXT_PARA, code
            elif data is not None:
                para, off = DGROUP_PARA, data
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
            entry["mz_relocation"] = site in relocs   # CS offset == load-module offset
        elif loc == "pointer32":
            cur = struct.unpack_from("<H", text, o)[0]
            struct.pack_into("<HH", text, o, (cur + off) & 0xFFFF, para)
            entry["mz_relocation"] = (site + 2) in relocs
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


def match_object(obj_bytes: bytes, source: pathlib.Path, at: int | None = None,
                 flags: str = "", model: str = "s") -> dict:
    global _IMAGE, _SYMBOLS
    if _IMAGE is None:
        _IMAGE, _SYMBOLS = unpacked_bytes(), SymbolMap()
    image, symbols = _IMAGE, _SYMBOLS
    text_src = source.read_text(encoding="latin1")
    segs = parse_directives(text_src)
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

    data_check = None
    if "_DATA" in segs and mod.segment_bytes("_DATA"):
        cand = mod.segment_bytes("_DATA")
        start = DGROUP_FILE + segs["_DATA"]
        orig = image[start:start + len(cand)]
        data_check = {"ds": segs["_DATA"], "length": len(cand),
                      "diffs": [i for i in range(len(cand)) if cand[i] != orig[i]]}
        dfx = mod.fixups_in("_DATA")
        if dfx:
            data_check["note"] = f"{len(dfx)} fixups inside _DATA not yet resolved by this tool"
            data_check["unverified_fixups"] = len(dfx)

    if hard_diffs or missing_reloc or (data_check and data_check["diffs"]):
        verdict = "MISMATCH"
    elif unresolved or (data_check and data_check.get("unverified_fixups")):
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
