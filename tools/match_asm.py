"""Strict assemble-and-compare for hand-written assembly modules (MATCHING_ASM).

Pipeline: assemble src/asm/<module>.asm with the pinned assembler
(layout/assembler.json, driven by tools/asm.py under DOSBox-X) -> parse the
OMF object (tools/omf.py) -> place its _TEXT at the module's original CS
address -> resolve EVERY fixup exactly as tools/match_function.py does (its
link() is reused, nothing is masked) -> require byte equality over the
module's FULL extent.

On top of match_function's rules, an assembly module must also satisfy:

* Placement is explicit: a directive comment `; @at 0x6f26` gives the CS
  offset of the module's _TEXT (hand-written modules name their procedures
  meaningfully, so they cannot be placed by census-id publics).
* Full extent: the compared length is the SEGDEF-declared _TEXT length, not
  just the bytes the object initializes; uninitialized tail bytes count as
  zeros (what TLINK writes) and must equal the original.
* Frames: a fixup whose target is DGROUP data (a DGROUP-segment or a
  data-symbol external) must use frame GROUP DGROUP, otherwise TLINK would
  produce a segment-relative offset that the symbol map does not describe.
  A fixup whose target is in _TEXT must use frame _TEXT / TARGET / LOCATION.
* Data: every non-_TEXT segment the module defines must be placed with a
  `; @seg <name> 0x....` directive (DGROUP-relative). Each such segment is
  compared over its full SEGDEF length with the original DGROUP bytes, and
  fixups inside data segments are rejected (not yet resolved by this tool).

Verdicts: EXACT / UNRESOLVED_FIXUPS / MISMATCH as in match_function, plus
ASSEMBLY_FAILED.

Usage:
    python tools/match_asm.py src/asm/sound.asm [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import asm  # noqa: E402
import match_function as mf  # noqa: E402
import omf  # noqa: E402
from symbols import SymbolMap, HDR  # noqa: E402

TEXT_FRAMES = {"segment:_TEXT", "target", "location"}


def parse_at(text: str) -> int | None:
    m = re.search(r"@at\s+(0x[0-9A-Fa-f]+|\d+)", text)
    return int(m.group(1), 0) if m else None


def match_object_asm(obj_bytes: bytes, source: pathlib.Path, key: str, options: str) -> dict:
    if mf._IMAGE is None:
        mf._IMAGE, mf._SYMBOLS = mf.unpacked_bytes(), SymbolMap()
    image, symbols = mf._IMAGE, mf._SYMBOLS
    text_src = source.read_text(encoding="latin1")
    at = parse_at(text_src)
    if at is None:
        raise SystemExit(f"{source}: no `; @at 0x....` placement directive")
    segs = mf.parse_directives(text_src)
    mod = omf.OmfReader().read(obj_bytes, source.stem)

    # Full _TEXT extent: SEGDEF length, zero-filled past the last LEDATA byte.
    text_len = mod.segment_length("_TEXT") or 0
    initialized = mod.segment_bytes("_TEXT") if "_TEXT" in mod.segments else b""
    if len(initialized) > text_len:
        raise SystemExit(f"{source}: _TEXT data runs past its SEGDEF length")
    mod.segments["_TEXT"] = initialized + b"\x00" * (text_len - len(initialized))
    linked, fixups = mf.link(mod, at, segs, symbols, image)
    original = image[HDR + at:HDR + at + len(linked)]

    # Frame discipline.
    frame_violations = []
    for f in fixups:
        if f["loc"] == "base16":
            continue
        tgt_is_text = (f["kind"] == "segment" and f["target"] == "_TEXT") or \
            (f["kind"] == "external" and symbols.resolve_code(f["target"]) is not None)
        if tgt_is_text:
            ok = f["frame"] in TEXT_FRAMES
        else:
            ok = f["frame"] == "group:DGROUP"
        if not ok:
            frame_violations.append({"cs": f["cs"], "target": f["target"], "frame": f["frame"]})

    diffs = [i for i in range(len(linked)) if linked[i] != original[i]]
    unresolved = [f for f in fixups if f.get("status") != "resolved"]
    unresolved_bytes = set()
    for f in unresolved:
        unresolved_bytes.update(range(f["offset"], f["offset"] + 2))
    hard_diffs = [d for d in diffs if d not in unresolved_bytes]
    missing_reloc = [f for f in fixups if f.get("mz_relocation") is False]

    # Every other segment must be placed and is compared over its full length.
    data_checks = []
    unplaced = []
    for name, length in mod.segment_lengths.items():
        if name == "_TEXT" or not length:
            continue
        if name not in segs:
            unplaced.append(name)
            continue
        cand = mod.segments.get(name, b"")
        cand = cand + b"\x00" * (length - len(cand))
        start = mf.DGROUP_FILE + segs[name]
        orig = image[start:start + length]
        data_checks.append({
            "segment": name, "ds": segs[name], "length": length,
            "diffs": [i for i in range(length) if cand[i] != orig[i]],
            "fixups": len(mod.fixups_in(name)),
        })
    data_bad = any(c["diffs"] for c in data_checks)
    data_unverified = any(c["fixups"] for c in data_checks)

    if hard_diffs or missing_reloc or data_bad or frame_violations or unplaced:
        verdict = "MISMATCH"
    elif unresolved or data_unverified:
        verdict = "UNRESOLVED_FIXUPS"
    else:
        verdict = "EXACT"

    return {
        "source": str(source).replace("\\", "/"),
        "kind": "MATCHING_ASM",
        "verdict": verdict,
        "assembler": key, "options": options,
        "cs_start": at, "cs_end": at + len(linked),
        "file_start": HDR + at, "file_end": HDR + at + len(linked),
        "length": len(linked),
        "segments": segs,
        "object_sha256": hashlib.sha256(obj_bytes).hexdigest(),
        "publics": mod.publics,
        "fixup_count": len(fixups),
        "unresolved_fixups": [{"target": f["target"], "kind": f["kind"], "cs": f["cs"]}
                              for f in unresolved],
        "missing_mz_relocations": [f["cs"] for f in missing_reloc],
        "frame_violations": frame_violations,
        "unplaced_segments": unplaced,
        "data_checks": data_checks,
        "diffs": [{"offset": d, "cs": at + d, "got": linked[d], "want": original[d]}
                  for d in hard_diffs[:64]],
        "diff_count": len(hard_diffs),
        "first_diff_context": mf.context(at + hard_diffs[0], image) if hard_diffs else [],
        "candidate_first_diff": (
            [f"{i.address:04x} {i.bytes.hex():12s} {i.mnemonic} {i.op_str}"
             for i in mf._md.disasm(linked[max(0, hard_diffs[0] - 4):hard_diffs[0] + 24],
                                    at + max(0, hard_diffs[0] - 4))]
            if hard_diffs else []),
        "fixups": fixups,
        "linked": linked,
    }


def assemble_and_match(sources, work: pathlib.Path | None = None,
                       key: str | None = None, options: str | None = None) -> list:
    """Assemble with the pinned assembler (or an explicit key/options, for
    identification experiments) and match every source."""
    pkey, popts = asm.pinned()
    key = key or pkey
    options = popts if options is None else options
    work = work or (ROOT / "build" / "asm_batch")
    objs = asm.assemble_many(sources, key, options, work=work)
    results = []
    for n, (src, obj) in enumerate(zip(sources, objs)):
        if obj is None:
            results.append({"source": str(src).replace("\\", "/"), "kind": "MATCHING_ASM",
                            "verdict": "ASSEMBLY_FAILED", "log": asm.log_for(work, n)})
            continue
        r = match_object_asm(obj.read_bytes(), pathlib.Path(src), key, options)
        listing = work / f"S{n + 1:04d}.LOG"
        r["log"] = listing.read_text(errors="replace") if listing.exists() else ""
        results.append(r)
    return results


def print_result(r: dict):
    if r["verdict"] == "ASSEMBLY_FAILED":
        print(f"ASSEMBLY_FAILED: {r['source']}\n{r['log']}")
        return
    print(f"{r['verdict']}: {r['source']} -> cs [{r['cs_start']:#06x},{r['cs_end']:#06x}) "
          f"file [{r['file_start']:#x},{r['file_end']:#x}) {r['length']} bytes, "
          f"{r['fixup_count']} fixups, {r['diff_count']} differing bytes "
          f"({r['assembler']} {r['options']})")
    for u in r["unresolved_fixups"]:
        print(f"  unresolved: {u}")
    for v in r["frame_violations"]:
        print(f"  frame violation: {v}")
    if r["unplaced_segments"]:
        print(f"  segments without @seg placement: {r['unplaced_segments']}")
    if r["missing_mz_relocations"]:
        print(f"  base16 fixups without MZ relocation at cs {r['missing_mz_relocations']}")
    for c in r["data_checks"]:
        print(f"  {c['segment']} @ ds {c['ds']:#06x} len {c['length']}: "
              f"{len(c['diffs'])} differing bytes, {c['fixups']} fixups"
              + (f" first at +{c['diffs'][0]:#x}" if c["diffs"] else ""))
    if r["diffs"]:
        print("  first diffs:", ", ".join(f"cs {d['cs']:#x} got {d['got']:02x} want {d['want']:02x}"
                                          for d in r["diffs"][:8]))
        print("  original:"); [print("    " + line) for line in r["first_diff_context"]]
        print("  candidate:"); [print("    " + line) for line in r["candidate_first_diff"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", type=pathlib.Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--assembler", default=None,
                    help="override the pinned assembler key (identification experiments only)")
    ap.add_argument("--options", default=None, help="override the pinned assembler options")
    args = ap.parse_args()
    results = assemble_and_match(args.sources, key=args.assembler, options=args.options)
    for r in results:
        if args.json:
            print(json.dumps({k: v for k, v in r.items() if k not in ("fixups", "linked")}, indent=1))
        else:
            print_result(r)
    sys.exit(0 if all(r["verdict"] == "EXACT" for r in results) else 1)


if __name__ == "__main__":
    main()
