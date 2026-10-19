"""Compile and strictly verify every recovered game source; feed the rebuild.

The game's C code is three translation units, src/DAVE.C, src/CONFIG.C and
src/HARDWARE.C (+ src/DAVE.H). Each is batch-compiled (tools/tcc.py) to ONE
object, placed by its own directives (`@at` for _TEXT, `@seg _DATA`, `@seg
_BSS`), and strictly matched (tools/match_function.py match_object): every
fixup resolved, _TEXT and the whole _DATA image compared, _BSS extent
checked. Addresses come from each unit's composition: references to the
unit's own data go through its segment bases, references to another unit's
(or an assembly module's) functions and variables through that object's
placed PUBDEFs, which verify_all() adds to the symbol map. On top:
  * census: a unit's publics are exactly the census C functions inside its
    extent, each at its census start;
  * layout: the units and assembly modules tile _TEXT [0x239,0x9413),
    _DATA [0xa8,0x1439) and the game _BSS [0x4c60,0x9ec8) with nothing
    between them but TLINK word-alignment pads (--json also writes
    <stem>_layout.json).
The linked bytes are written to build/matched/<stem>.bin, which is what
tools/reconstruct.py uses for MATCHING_C regions -- the rebuilt image's
matched code therefore really comes from the compiler, not from raw extracts.

--sync rewrites layout/manifest.json's code-area ownership from the verdicts:
every MATCHING_C region is re-derived (id = unit stem, extent = linked
extent), the bytes between them stay RAW_UNKNOWN, adjacent RAW_UNKNOWN
regions are coalesced. Extents must coincide with census function
boundaries. Then extract_raw.py + reconstruct.py run; any failure restores
the previous manifest.

src/asm/*.asm (hand-written assembly) take a separate, verification-only
path: see verify_asm() below; their report goes to <json stem>_asm.json.

Usage: python tools/verify_sources.py [--sync] [--json build/verify.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import match_function as mf  # noqa: E402
import reconstruct  # noqa: E402
import tcc  # noqa: E402

SRC = ROOT / "src"                 # translation units: src/<UNIT>.C (+ src/DAVE.H)
OUT = ROOT / "build" / "matched"
C0S_END_CS = 0x0239                # first game byte: _main (C0S _TEXT ends here)
GAME_DATA_DS = 0x00A8              # C0S _DATA ends here (docs/data-layout.md)


def unit_sources():
    return sorted(p for p in SRC.glob("*.[cC]") if p.suffix in (".C", ".c"))


def rel(p: pathlib.Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def verify_all(asm_results=()):
    """Compile every unit, place each object by its directives, add every
    placed object's PUBDEFs (units and assembly modules) to the symbol map,
    then strictly match each unit against that map: a reference from one unit
    to another's function or variable resolves to the address that the other
    unit's own composition gives it."""
    sources = unit_sources()
    objs = tcc.compile_many(sources, work=ROOT / "build" / "verify_batch")
    OUT.mkdir(parents=True, exist_ok=True)
    if mf._IMAGE is None:
        mf._IMAGE, mf._SYMBOLS = mf.unpacked_bytes(), mf.SymbolMap()
    symbols = mf._SYMBOLS.copy()
    for r in asm_results:
        for p in r.get("publics", []):
            if p["segment"] == "_TEXT":
                symbols.define(p["name"], "code", r["cs_start"] + p["offset"], r["source"])
            else:
                symbols.define(p["name"], "data", r["segments"][p["segment"]] + p["offset"], r["source"])
    mods = {}
    for src, obj in zip(sources, objs):
        if obj is None:
            continue
        text = src.read_text(encoding="latin1")
        mod = mf.omf.OmfReader().read(obj.read_bytes(), src.stem)
        at = mf.parse_at(text)
        if at is None:
            raise SystemExit(f"{rel(src)}: no `/* @at 0x.... */` placement directive")
        for name, kind, addr in mf.object_symbols(mod, at, mf.parse_directives(text)):
            symbols.define(name, kind, addr, rel(src))
        mods[src] = mod
    results = []
    for i, (src, obj) in enumerate(zip(sources, objs)):
        if obj is None:
            log = (ROOT / "build" / "verify_batch" / f"S{i + 1:04d}.LOG")
            results.append({"source": rel(src), "verdict": "COMPILE_FAILED",
                            "log": log.read_text(errors="replace") if log.exists() else ""})
            continue
        r = mf.match_object(obj.read_bytes(), src, symbols=symbols)
        r["source"] = rel(src)
        r["census"] = census_check(r)
        if r["census"]["problems"] and r["verdict"] == "EXACT":
            r["verdict"] = "MISMATCH"
        data_linked = r.pop("data_linked", None)
        text_linked = r.pop("text_linked", None)
        if r["verdict"] == "EXACT":
            # the compiler's linked bytes (equal to the image: that is what EXACT means)
            (OUT / f"{src.stem}.bin").write_bytes(text_linked)
            if data_linked is not None:
                (OUT / f"{src.stem}_DATA.bin").write_bytes(data_linked)
        results.append(r)
    return results


def census_check(r) -> dict:
    """A unit's functions must be exactly the census C functions inside its
    _TEXT extent, each public landing on its census start."""
    census = json.loads((ROOT / "docs" / "function-census.json").read_text())
    inside = {f["cs_start"]: f["id"] for f in census["functions"]
              if r["cs_start"] <= f["cs_start"] < r["cs_end"]}
    problems = []
    publics = {r["cs_start"] + p["offset"]: p["name"] for p in r["publics"] if p["segment"] == "_TEXT"}
    for cs, name in sorted(publics.items()):
        if cs not in inside:
            problems.append(f"{name} at cs {cs:#06x} is not a census function start")
    for cs, fid in sorted(inside.items()):
        if cs not in publics:
            problems.append(f"census {fid} (cs {cs:#06x}) is not a public of this unit")
    lang = {f["id"]: f["lang"] for f in census["functions"]}
    non_c = [fid for fid in inside.values() if not lang[fid].startswith("C")]
    if non_c:
        problems.append(f"non-C census functions inside the unit: {non_c}")
    return {"functions": [{"cs": cs, "id": inside.get(cs), "name": n} for cs, n in sorted(publics.items())],
            "problems": problems}


def tile(name, ranges, lo, hi, image_base=None) -> dict:
    """Do the placed ranges cover [lo, hi) in order with nothing between them
    except TLINK's word-alignment pads (one byte before an even start, zero
    in the original when it is file data)?"""
    out = {"segment": name, "range": [lo, hi], "pieces": [], "problems": []}
    pos = lo
    for start, end, who in sorted(ranges):
        if start < pos:
            out["problems"].append(f"{who} [{start:#06x},{end:#06x}) overlaps the previous piece")
        elif start > pos:
            pad_ok = start - pos == 1 and start % 2 == 0
            if pad_ok and image_base is not None:
                pad_ok = mf._IMAGE[image_base + pos] == 0
            if pad_ok:
                out["pieces"].append({"start": pos, "end": start, "owner": "TLINK word-alignment pad"})
            else:
                out["problems"].append(f"gap [{pos:#06x},{start:#06x}) before {who}")
        out["pieces"].append({"start": start, "end": end, "owner": who})
        pos = max(pos, end)
    if pos != hi:
        out["problems"].append(f"pieces end at {pos:#06x}, expected {hi:#06x}")
    return out


def composition(results, asm_results) -> list:
    """Whole-program layout check of the C units and the assembly modules:
    _TEXT from the end of C0S to the end of the assembly, _DATA from the end
    of C0S's _DATA to the end of the assembly's _DATA, and the game _BSS."""
    units = [r for r in results if r["verdict"] == "EXACT"]
    asms = [r for r in asm_results if r["verdict"] == "EXACT"]
    text = [(r["cs_start"], r["cs_end"], r["source"]) for r in units + asms]
    data = [(r["data_check"]["ds"], r["data_check"]["ds"] + r["data_check"]["length"], r["source"])
            for r in units if r.get("data_check")]
    for r in asms:
        for c in r.get("data_checks", []):
            data.append((c["ds"], c["ds"] + c["length"], f"{r['source']} {c['segment']}"))
    bss = [(r["bss_check"]["ds"], r["bss_check"]["end"], r["source"]) for r in units if r.get("bss_check")]
    text_end = max((e for _, e, _ in text), default=C0S_END_CS)
    data_end = max((e for _, e, _ in data), default=GAME_DATA_DS)
    return [tile("_TEXT", text, C0S_END_CS, text_end, image_base=mf.HDR),
            tile("_DATA", data, GAME_DATA_DS, data_end, image_base=mf.DGROUP_FILE),
            tile("_BSS", bss, *mf.GAME_BSS)]


ASM_RANGE_CS = (0x6F25, 0x9413)   # hand-written assembly (docs/function-census.md, layout/assembler.json)


def sync_manifest(results, asm_results=(), composition_result=None):
    bounds = mf.census_boundaries()
    manifest = mf.load_manifest()
    backup = mf.MANIFEST_PATH.read_text()
    # 1. dissolve existing MATCHING_C regions back into RAW_UNKNOWN
    regions = []
    for r in sorted(manifest["regions"], key=lambda r: r["start"]):
        if r["kind"] in ("MATCHING_C", "MATCHING_ASM") or (
                r["kind"] == "PADDING" and r.get("padding_reason") in ("tlink_word_align_asm",
                                                                       "tlink_word_align_data")):
            r = {"id": "tmp", "start": r["start"], "end": r["end"], "kind": "RAW_UNKNOWN",
                 "classification": "unknown"}
        if regions and regions[-1]["kind"] == "RAW_UNKNOWN" and r["kind"] == "RAW_UNKNOWN" \
                and regions[-1]["end"] == r["start"]:
            regions[-1]["end"] = r["end"]
        else:
            regions.append(dict(r))
    # 2. carve each EXACT unit's _TEXT out of RAW_UNKNOWN
    for res in sorted((r for r in results if r["verdict"] == "EXACT"), key=lambda r: r["file_start"]):
        if res["cs_start"] not in bounds or res["cs_end"] not in bounds:
            raise SystemExit(f"{res['source']}: extent [{res['cs_start']:#x},{res['cs_end']:#x}) "
                             "is not on census function boundaries")
        a, b = res["file_start"], res["file_end"]
        idx = next((i for i, r in enumerate(regions)
                    if r["kind"] == "RAW_UNKNOWN" and r["start"] <= a and b <= r["end"]), None)
        if idx is None:
            raise SystemExit(f"{res['source']}: [{a:#x},{b:#x}) is not inside one RAW_UNKNOWN region")
        old = regions[idx]
        stem = pathlib.Path(res["source"]).stem
        new = []
        if old["start"] < a:
            new.append({**old, "end": a})
        new.append({
            "id": stem, "start": a, "end": b, "kind": "MATCHING_C", "classification": "code",
            "source": res["source"], "compile_flags": {"model": res["model"], "flags": res["flags"]},
            "object_sha256": res["object_sha256"], "matching_status": "EXACT",
            "matching_status_note": "tools/verify_sources.py: strict link, every fixup resolved, "
                                    f"{res['fixup_count']} fixups, 0 differing bytes",
            "artifact": f"build/matched/{stem}.bin",
        })
        if b < old["end"]:
            new.append({**old, "start": b})
        regions[idx:idx + 1] = new
    # 3. carve each EXACT assembly module (its whole _TEXT extent)
    image = mf.unpacked_bytes()
    for res in sorted((r for r in asm_results if r["verdict"] == "EXACT"), key=lambda r: r["cs_start"]):
        if not (ASM_RANGE_CS[0] <= res["cs_start"] and res["cs_end"] <= ASM_RANGE_CS[1]):
            raise SystemExit(f"{res['source']}: outside the assembly range")
        a, b = res["cs_start"] + 0x200, res["cs_end"] + 0x200
        idx = next((i for i, r in enumerate(regions)
                    if r["kind"] == "RAW_UNKNOWN" and r["start"] <= a and b <= r["end"]), None)
        if idx is None:
            raise SystemExit(f"{res['source']}: [{a:#x},{b:#x}) is not inside one RAW_UNKNOWN region")
        old = regions[idx]
        stem = pathlib.Path(res["source"]).stem
        new = []
        if old["start"] < a:
            new.append({**old, "end": a})
        new.append({
            "id": stem, "start": a, "end": b, "kind": "MATCHING_ASM", "classification": "code",
            "source": res["source"], "assembler": f"{res.get('assembler')} {res.get('options')}",
            "matching_status": "EXACT",
            "matching_status_note": "tools/match_asm.py: strict link, every fixup resolved, "
                                    f"{res['fixup_count']} fixups; module _DATA compared with DGROUP",
            "artifact": f"build/matched/{stem}.bin",
        })
        if b < old["end"]:
            new.append({**old, "start": b})
        regions[idx:idx + 1] = new
    # 4. a single zero byte right before an assembly module is TLINK's WORD
    #    alignment of that module's _TEXT (TASM .MODEL small), not unknown code
    for i, r in enumerate(regions[:-1]):
        if (r["kind"] == "RAW_UNKNOWN" and r["end"] - r["start"] == 1
                and regions[i + 1]["kind"] == "MATCHING_ASM" and image[r["start"]] == 0
                and regions[i + 1]["start"] % 2 == 0):
            r.update(kind="PADDING", classification="padding", padding_reason="tlink_word_align_asm",
                     description="TLINK word alignment before a WORD-aligned TASM _TEXT")

    def carve(a, b, region, what):
        idx = next((i for i, r in enumerate(regions)
                    if r["kind"] == "RAW_UNKNOWN" and r["start"] <= a and b <= r["end"]), None)
        if idx is None:
            raise SystemExit(f"{what}: [{a:#x},{b:#x}) is not inside one RAW_UNKNOWN region")
        old = regions[idx]
        new = ([{**old, "end": a}] if old["start"] < a else []) + [region] + \
              ([{**old, "start": b}] if b < old["end"] else [])
        regions[idx:idx + 1] = new

    # 5. each EXACT unit's _DATA (initialised globals, local-aggregate images,
    #    string pool), rebuilt from the compiler's linked _DATA image
    for res in sorted((r for r in results if r["verdict"] == "EXACT" and r.get("data_check")),
                      key=lambda r: r["data_check"]["ds"]):
        d = res["data_check"]
        stem = pathlib.Path(res["source"]).stem
        a = mf.DGROUP_FILE + d["ds"]
        carve(a, a + d["length"], {
            "id": f"{stem}_DATA", "start": a, "end": a + d["length"], "kind": "MATCHING_C",
            "classification": "data", "source": res["source"],
            "compile_flags": {"model": res["model"], "flags": res["flags"]},
            "object_sha256": res["object_sha256"], "matching_status": "EXACT",
            "matching_status_note": f"tools/verify_sources.py: the unit's whole _DATA image at DS "
                                    f"[{d['ds']:#06x},{d['ds'] + d['length']:#06x}), {d['fixups']} "
                                    "fixups resolved, 0 differing bytes",
            "artifact": f"build/matched/{stem}_DATA.bin"}, res["source"])
    # 6. TLINK's word-alignment pads between DGROUP contributions, as proven by
    #    the composition check (one zero byte before an even start)
    for c in composition_result or ():
        if c["segment"] != "_DATA":
            continue
        for p in c["pieces"]:
            if p["owner"] == "TLINK word-alignment pad":
                a = mf.DGROUP_FILE + p["start"]
                carve(a, a + 1, {"id": f"PAD_{a:X}", "start": a, "end": a + 1, "kind": "PADDING",
                                 "classification": "padding", "padding_reason": "tlink_word_align_data",
                                 "description": "TLINK word alignment of the next module's _DATA",
                                 "artifact": f"raw/PAD_{a:X}.bin"}, "pad")
    for r in regions:
        if r["kind"] == "PADDING" and r.get("padding_reason") == "tlink_word_align_asm":
            r["id"] = f"PAD_{r['start']:X}"
            r["artifact"] = f"raw/{r['id']}.bin"
        if r["kind"] == "RAW_UNKNOWN":
            r["id"] = f"RAW_{r['start']:X}_{r['end']:X}"
            r["artifact"] = f"raw/{r['id']}.bin"
    manifest["regions"] = regions
    reconstruct.validate_ownership(manifest)
    mf.MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        for tool in ("extract_raw.py", "reconstruct.py"):
            p = subprocess.run([sys.executable, str(ROOT / "tools" / tool)], cwd=ROOT,
                               capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(f"{tool} failed:\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    except Exception:
        mf.MANIFEST_PATH.write_text(backup)
        raise


# ---------------------------------------------------------------------------
# Hand-written assembly: src/asm/*.asm (separate path, verification only).
#
# Each module is assembled with the pinned assembler (layout/assembler.json,
# tools/asm.py) and strictly matched by tools/match_asm.py (match_function's
# link(), full SEGDEF extent, frame checks, _DATA compared with DGROUP). The
# assembler's linked bytes go to build/matched/<stem>.bin, ready for
# MATCHING_ASM regions. These results never feed --sync (the C carving
# below); MATCHING_ASM manifest regions are applied separately.

ASM_SRC = ROOT / "src" / "asm"


def verify_asm():
    import match_asm  # noqa: E402  (pulls in tools/asm.py only when needed)
    sources = sorted(ASM_SRC.glob("*.asm"))
    if not sources:
        return []
    # The modules reference C-owned globals by their C (storage) names, so the
    # C units' placed publics must be known first: compile the units and add
    # every symbol their own composition places (same rule as verify_all).
    if mf._IMAGE is None:
        mf._IMAGE, mf._SYMBOLS = mf.unpacked_bytes(), mf.SymbolMap()
    units = unit_sources()
    for src, obj in zip(units, tcc.compile_many(units, work=ROOT / "build" / "verify_asm_units")):
        if obj is None:
            continue
        text = src.read_text(encoding="latin1")
        mod = mf.omf.OmfReader().read(obj.read_bytes(), src.stem)
        at = mf.parse_at(text)
        if at is not None:
            for name, kind, addr in mf.object_symbols(mod, at, mf.parse_directives(text)):
                mf._SYMBOLS.define(name, kind, addr, rel(src))
    results = match_asm.assemble_and_match(sources, work=ROOT / "build" / "verify_asm_batch")
    OUT.mkdir(parents=True, exist_ok=True)
    for src, r in zip(sources, results):
        r["source"] = str(src.relative_to(ROOT)).replace("\\", "/")
        linked = r.pop("linked", None)
        if r["verdict"] == "EXACT":
            (OUT / f"{src.stem}.bin").write_bytes(linked)
    return results


def report_asm(results) -> int:
    bad = 0
    for r in results:
        if r["verdict"] == "EXACT":
            data = ", ".join(f"{c['segment']} ds [{c['ds']:#06x},{c['ds'] + c['length']:#06x})"
                             for c in r["data_checks"])
            print(f"EXACT     {r['source']}  cs [{r['cs_start']:#06x},{r['cs_end']:#06x}) "
                  f"{r['length']} bytes, {r['fixup_count']} fixups"
                  + (f"; {data}" if data else "") + f" ({r['assembler']} {r['options']})")
        else:
            bad += 1
            print(f"{r['verdict']:9s} {r['source']}  {r.get('diff_count', '')}")
    if results:
        print(f"{len(results) - bad}/{len(results)} assembly modules EXACT, "
              f"{sum(r['length'] for r in results if r['verdict'] == 'EXACT')} bytes")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--json", default=None)
    ap.add_argument("--json-asm", default=None,
                    help="report for src/asm/*.asm (default: <--json stem>_asm.json)")
    args = ap.parse_args()
    asm_results = verify_asm()
    asm_bad = report_asm(asm_results)
    asm_json = args.json_asm or (str(pathlib.Path(args.json).with_name(
        pathlib.Path(args.json).stem + "_asm.json")) if args.json else None)
    if asm_json:
        pathlib.Path(asm_json).write_text(json.dumps(
            [{k: v for k, v in r.items() if k != "fixups"} for r in asm_results], indent=1))
    results = verify_all(asm_results)
    bad = 0
    for r in results:
        if r["verdict"] == "EXACT":
            d, b = r.get("data_check"), r.get("bss_check")
            print(f"EXACT     {r['source']}  cs [{r['cs_start']:#06x},{r['cs_end']:#06x}) "
                  f"{r['length']} bytes, {len(r['census']['functions'])} functions, "
                  f"{r['fixup_count']} fixups"
                  + (f"; _DATA ds [{d['ds']:#06x},{d['ds'] + d['length']:#06x})" if d else "")
                  + (f"; _BSS ds [{b['ds']:#06x},{b['end']:#06x})" if b else ""))
        else:
            bad += 1
            extra = r.get("diff_count", "")
            print(f"{r['verdict']:9s} {r['source']}  {extra}")
            for p in r.get("census", {}).get("problems", []):
                print(f"          census: {p}")
            if r.get("unplaced_segments"):
                print(f"          unplaced segments: {r['unplaced_segments']}")
            if r.get("data_check") and r["data_check"]["diffs"]:
                print(f"          _DATA differs at {len(r['data_check']['diffs'])} bytes")
    print(f"{len(results) - bad}/{len(results)} sources EXACT, "
          f"{sum(r['length'] for r in results if r['verdict'] == 'EXACT')} bytes")
    comp = composition(results, asm_results)
    for c in comp:
        lo, hi = c["range"]
        print(f"layout {c['segment']:5s} [{lo:#06x},{hi:#06x}): {len(c['pieces'])} pieces"
              + ("" if not c["problems"] else "; " + "; ".join(c["problems"])))
        bad += bool(c["problems"])
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            [{k: v for k, v in r.items() if k != "fixups"} for r in results], indent=1))
        pathlib.Path(args.json).with_name(pathlib.Path(args.json).stem + "_layout.json").write_text(
            json.dumps(comp, indent=1))
    if args.sync:
        if bad:
            raise SystemExit("refusing to sync: not every source is EXACT")
        if asm_bad:
            raise SystemExit("refusing to sync: not every assembly module is EXACT")
        sync_manifest(results, asm_results, comp)
        print("manifest synced; reconstruction exact")
    sys.exit(1 if bad or asm_bad else 0)


if __name__ == "__main__":
    main()
