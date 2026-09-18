"""Scan a Turbo C++ 1.00 runtime library for exact-modulo-fixups contributions
to the unpacked Dangerous Dave load module.

Generalizes tools/recover_startup_binding.py's technique (which identified
STARTUP_C0S) from "one known object at one known offset" to "many library
member modules against many candidate offsets in the RAW_UNKNOWN region(s)
of layout/manifest.json".

Proof bar (same as STARTUP_C0S, see docs/matching-phase.md /
docs/vision.md): a module's `_TEXT` segment counts as a match against a
candidate byte range only if EVERY differing byte falls inside a byte range
declared by one of that module's own FIXUPP records for `_TEXT`. Zero
unexplained differences. "Mostly matches" is not a match.

Search strategy (candidate offsets are expensive to try blindly across a
~172KB region x 300+ modules):

1. Anchor on docs/function-census.json's 193 candidate function boundaries.
   Any library module whose `_TEXT` length equals a census function's
   `size` is compared directly at that function's file offset. Cheap:
   O(census functions) dict lookups by exact size.
2. For modules not matched that way (frameless/leaf functions the naive
   census prologue-scan cannot see -- e.g. INPORT/OUTPORT, which have no
   `sub sp` and are far shorter than most census entries but still begin
   with the `55 8B EC` prologue the census *does* scan for, so in practice
   most turn up in step 1 too), fall back to a literal byte-string search
   (memmem-style, via `bytes.find`) for the module's own `_TEXT` bytes as
   the search key, across the full current RAW_UNKNOWN extent. This finds
   a module regardless of census boundaries, at the cost of being a full
   literal match (a real modulo-fixups match with actual fixups therefore
   is NOT found by this fallback unless the fixup bytes happen to already
   equal the original library's placeholder bytes -- step 1 remains the
   primary path for anything with real fixups). Only modules above a
   minimum size are tried this way, to keep the false-positive rate low.

A match is only accepted for promotion if:
  - every non-matching byte is explained by a FIXUPP location (may be zero
    such bytes, as for INPORT/OUTPORT), AND
  - the candidate range does not overlap a range already promoted in this
    same run (first match wins; ties/overlaps are logged as conflicts, not
    silently resolved), AND
  - (for the memmem fallback path only) the match is unique within the
    current RAW_UNKNOWN bytes -- an ambiguous literal match is not
    trustworthy enough to promote.

Usage:
    python tools/library_scanner.py [--library CS.LIB] [--apply] [--min-size N]

Without --apply, only prints/reports findings (docs/library-scan-evidence.json
and .md are still written either way, marked with whether they were applied).
With --apply, promotes every accepted match into layout/manifest.json,
regenerates raw/ extracts, and reruns the full test suite + reconstruction
check; on any failure it restores the original manifest.json and raw/ files
and aborts loudly (never leaves the manifest broken).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import omf  # noqa: E402
import reconstruct  # noqa: E402

MANIFEST_PATH = ROOT / "layout" / "manifest.json"
CENSUS_PATH = ROOT / "docs" / "function-census.json"
UNPACKED_PATH = ROOT / "build" / "DAVE_unpacked.exe"

# Minimum _TEXT length to attempt the memmem fallback path. Below this, a
# literal-byte match is too likely to be coincidental (or to collide with
# unrelated code that merely starts the same way) to trust without a census
# anchor. Chosen generously above the shortest real library routines seen
# so far (INPORT's two sub-functions are 9/11 bytes each, but the *module*
# they come from is 20 bytes and matched via census anchoring in practice).
MEMMEM_MIN_SIZE = 16

# Matches a trailing "_<HEX>_<HEX>" id suffix so a residual RAW_UNKNOWN
# region's id can be rebuilt from its canonical base rather than having a
# new suffix appended on top of an already-suffixed id every time it is
# re-split (which would grow unboundedly across repeated promotion runs and
# eventually exceed a filesystem's path length limit for raw/<id>.bin).
_RESIDUAL_SUFFIX_RE = re.compile(r"(_[0-9A-F]+_[0-9A-F]+)+$")


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def load_census() -> list:
    return json.loads(CENSUS_PATH.read_text())["functions"]


def unpacked_bytes() -> bytes:
    manifest = load_manifest()
    data = UNPACKED_PATH.read_bytes()
    expected = manifest["unpacked_original"]
    if len(data) != expected["size"] or hashlib.md5(data).hexdigest() != expected["md5"]:
        raise SystemExit("build/DAVE_unpacked.exe does not match the pinned specimen")
    return data


def raw_unknown_regions(manifest: dict) -> list:
    """[(start, end)] for every current RAW_UNKNOWN region, sorted."""
    return sorted(
        (r["start"], r["end"]) for r in manifest["regions"] if r["kind"] == "RAW_UNKNOWN"
    )


def in_unknown(offset: int, length: int, unknown_regions: list) -> bool:
    end = offset + length
    return any(start <= offset and end <= region_end for start, region_end in unknown_regions)


def load_library_modules(lib_path: pathlib.Path) -> list:
    """[(name, ObjectModule, raw_module_bytes)] for every parseable member."""
    reader = omf.OmfReader()
    data = lib_path.read_bytes()
    out = []
    for name, blob in reader.split_library(data):
        try:
            mod = reader.read(blob, name)
        except omf.MatchError as exc:
            out.append((name, None, blob, str(exc)))
            continue
        out.append((name, mod, blob, None))
    return out


def fixup_covered_bytes(mod: omf.ObjectModule, segment: str) -> set:
    covered = set()
    for fx in mod.fixups_in(segment):
        covered.update(range(fx["offset"], fx["offset"] + fx["width"]))
    return covered


def compare_modulo_fixups(candidate: bytes, seg_bytes: bytes, covered: set) -> list:
    """Sorted list of unexplained differing byte offsets (empty == match)."""
    n = len(seg_bytes)
    diffs = [i for i in range(n) if candidate[i] != seg_bytes[i]]
    return [i for i in diffs if i not in covered]


def find_all(haystack: bytes, needle: bytes, lo: int, hi: int) -> list:
    """All start offsets (within [lo,hi)) where `needle` occurs in
    haystack[lo:hi], as absolute offsets into `haystack`."""
    out = []
    start = lo
    while True:
        idx = haystack.find(needle, start, hi)
        if idx < 0:
            break
        out.append(idx)
        start = idx + 1
    return out


def scan(lib_name: str, min_size: int) -> dict:
    lib_path = ROOT / "toolchain" / "LIB" / lib_name
    manifest = load_manifest()
    data = unpacked_bytes()
    unknown_regions = raw_unknown_regions(manifest)
    census = load_census()
    census_by_size: dict = {}
    for fn in census:
        census_by_size.setdefault(fn["size"], []).append(fn)

    modules = load_library_modules(lib_path)

    accepted = []       # list of match dicts, promoted
    rejected = []        # candidates that were tried and failed/ambiguous
    parse_errors = []
    claimed = []          # (start, end) already accepted, to prevent overlap

    def overlaps_claimed(start, end):
        return any(not (end <= cs or start >= ce) for cs, ce in claimed)

    for name, mod, blob, err in modules:
        if err is not None:
            parse_errors.append({"module": name, "error": err})
            continue
        seg = mod.segments.get("_TEXT")
        if not seg:
            continue
        n = len(seg)
        covered = fixup_covered_bytes(mod, "_TEXT")
        module_sha256 = hashlib.sha256(blob).hexdigest()

        tried_offsets = set()

        # Step 1: census-size anchoring.
        for fn in census_by_size.get(n, []):
            offset = fn["start"]
            tried_offsets.add(offset)
            if offset in tried_offsets and not in_unknown(offset, n, unknown_regions):
                continue
            candidate = data[offset:offset + n]
            unexplained = compare_modulo_fixups(candidate, seg, covered)
            if unexplained:
                rejected.append({
                    "module": name, "method": "census_size_anchor",
                    "census_function": fn["id"], "offset": offset, "size": n,
                    "unexplained_diff_count": len(unexplained),
                })
                continue
            if overlaps_claimed(offset, offset + n):
                rejected.append({
                    "module": name, "method": "census_size_anchor",
                    "offset": offset, "size": n,
                    "reason": "overlaps a previously accepted match",
                })
                continue
            accepted.append({
                "module": name, "method": "census_size_anchor",
                "census_function": fn["id"],
                "start": offset, "end": offset + n, "size": n,
                "fixup_covered_bytes": len(covered),
                "unexplained_diffs": 0,
                "module_sha256": module_sha256,
            })
            claimed.append((offset, offset + n))

        if any(a["module"] == name for a in accepted):
            continue

        # Step 2: memmem fallback for modules not resolved via census.
        if n < min_size:
            continue
        for region_start, region_end in unknown_regions:
            hits = find_all(data, seg, region_start, region_end)
            hits = [h for h in hits if h not in tried_offsets]
            if not hits:
                continue
            if len(hits) > 1:
                rejected.append({
                    "module": name, "method": "memmem", "size": n,
                    "reason": f"ambiguous: {len(hits)} literal occurrences",
                    "offsets": hits[:10],
                })
                continue
            offset = hits[0]
            if overlaps_claimed(offset, offset + n):
                rejected.append({
                    "module": name, "method": "memmem", "offset": offset,
                    "size": n, "reason": "overlaps a previously accepted match",
                })
                continue
            # A literal memmem hit is by construction an exact byte match
            # (0 diffs), so it trivially satisfies "modulo fixups" too.
            accepted.append({
                "module": name, "method": "memmem",
                "start": offset, "end": offset + n, "size": n,
                "fixup_covered_bytes": len(covered),
                "unexplained_diffs": 0,
                "module_sha256": module_sha256,
            })
            claimed.append((offset, offset + n))

    accepted.sort(key=lambda m: m["start"])
    return {
        "library": lib_name,
        "library_sha256": hashlib.sha256(lib_path.read_bytes()).hexdigest(),
        "module_count": len(modules),
        "parse_errors": parse_errors,
        "accepted": accepted,
        "rejected_count": len(rejected),
        "rejected_sample": rejected[:40],
    }


def apply_matches(result: dict) -> dict:
    """Promote every accepted match into layout/manifest.json. Verifies with
    the full test suite + reconstruction before committing; restores the
    original manifest/raw files and raises on any failure."""
    manifest_backup = MANIFEST_PATH.read_text()
    raw_dir = ROOT / "raw"
    raw_backup = {p.name: p.read_bytes() for p in raw_dir.glob("*.bin")}

    manifest = load_manifest()
    regions = manifest["regions"]

    for match in result["accepted"]:
        start, end = match["start"], match["end"]
        # Find the RAW_UNKNOWN region containing [start, end).
        idx = next(
            i for i, r in enumerate(regions)
            if r["kind"] == "RAW_UNKNOWN" and r["start"] <= start and end <= r["end"]
        )
        old = regions[idx]
        new_regions = []
        if old["start"] < start:
            # Derive the residual id from the ORIGINAL region's base id plus
            # its own (new, final) [start,end) -- never from the old id
            # string, which would otherwise accumulate one suffix per split
            # across repeated promotions and eventually exceed Windows'
            # filename length limit (raw/<id>.bin).
            base_id = _RESIDUAL_SUFFIX_RE.sub("", old["id"])
            new_regions.append({**old, "end": start,
                                 "id": f"{base_id}_{old['start']:X}_{start:X}"})
        new_id = f"LIB_{match['module']}_{start:X}"
        new_regions.append({
            "id": new_id,
            "start": start,
            "end": end,
            "kind": "KNOWN_LIBRARY",
            "classification": "code",
            "library": "Borland Turbo C++ 1.00 runtime (small memory model)",
            "library_module": f"CS.LIB:{match['module']}",
            "module_sha256": match["module_sha256"],
            "description": (
                f"Turbo C++ 1.00 CS.LIB member module {match['module']!r}, "
                f"identified by tools/library_scanner.py: its _TEXT segment "
                f"({match['size']} bytes) matches file offset "
                f"[{start:#x},{end:#x}) with zero unexplained differences "
                f"(method={match['method']}"
                + (f", anchored on census function {match['census_function']}"
                   if "census_function" in match else "")
                + f", {match['fixup_covered_bytes']} fixup-covered bytes)."
            ),
            "matching_status": "EXACT_MODULO_FIXUPS",
            "matching_status_note": (
                "See docs/library-scan-evidence.json for the full search "
                "methodology and per-module results."
            ),
            "artifact": f"raw/{new_id}.bin",
        })
        if end < old["end"]:
            base_id = _RESIDUAL_SUFFIX_RE.sub("", old["id"])
            new_regions.append({**old, "start": end, "id": f"{base_id}_{end:X}_{old['end']:X}"})
        regions[idx:idx + 1] = new_regions

    regions.sort(key=lambda r: r["start"])
    manifest["regions"] = regions

    # Structural validation before touching disk state further.
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
        extract = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "extract_raw.py")],
            cwd=ROOT, capture_output=True, text=True)
        if extract.returncode != 0:
            raise RuntimeError(
                f"extract_raw.py failed:\n{extract.stdout}\n{extract.stderr}")
        recon = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "reconstruct.py")],
            cwd=ROOT, capture_output=True, text=True)
        if recon.returncode != 0:
            raise RuntimeError(f"reconstruct.py failed:\n{recon.stdout}\n{recon.stderr}")
        recon_report = json.loads(recon.stdout)
        if not recon_report.get("ok"):
            raise RuntimeError(f"reconstruction failed: {recon.stdout}")
        tests = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ROOT, capture_output=True, text=True)
        if tests.returncode != 0:
            raise RuntimeError(f"test suite failed:\n{tests.stdout}\n{tests.stderr}")
    except Exception:
        restore()
        raise

    return {"applied": True, "region_count": len(regions)}


def write_evidence(result: dict, applied: bool):
    result = dict(result)
    result["applied"] = applied
    (ROOT / "docs" / "library-scan-evidence.json").write_text(json.dumps(result, indent=2) + "\n")

    lines = [
        "# Library contribution scan evidence",
        "",
        f"Generated by `tools/library_scanner.py` against `{result['library']}` "
        f"(sha256 `{result['library_sha256']}`).",
        "",
        f"- Library member modules: {result['module_count']} "
        f"({len(result['parse_errors'])} failed to parse)",
        f"- Accepted matches (exact modulo fixups, non-overlapping): "
        f"{len(result['accepted'])}",
        f"- Rejected candidates (ambiguous / unexplained diffs / overlap): "
        f"{result['rejected_count']}",
        f"- Applied to layout/manifest.json: {applied}",
        "",
        "## Methodology",
        "",
        "1. Anchor candidate offsets on `docs/function-census.json`'s 193 "
        "prologue-scanned function boundaries: any library module whose "
        "`_TEXT` length exactly equals a census function's size is compared "
        "directly at that function's file offset.",
        "2. For modules not resolved that way, fall back to a literal "
        "byte-string search (memmem-style) for the module's own `_TEXT` "
        "bytes across the current `RAW_UNKNOWN` extent(s), requiring a "
        "*unique* occurrence (an ambiguous match is rejected, not guessed).",
        "3. A match counts only if every differing byte between the "
        "candidate range and the library module's `_TEXT` segment is "
        "explained by that module's own FIXUPP records (zero unexplained "
        "differences) -- the same bar `tools/recover_startup_binding.py` "
        "used to identify `STARTUP_C0S`.",
        "4. Overlapping matches are resolved first-come-first-served within "
        "a single scan run and any conflict is logged, never silently "
        "picked.",
        "",
        "## Accepted matches",
        "",
        "| module | file offset | size | method | fixup-covered bytes |",
        "|---|---|---|---|---|",
    ]
    for m in result["accepted"]:
        lines.append(
            f"| {m['module']} | [{m['start']:#x},{m['end']:#x}) | {m['size']} "
            f"| {m['method']} | {m['fixup_covered_bytes']} |"
        )
    lines.append("")
    (ROOT / "docs" / "library-scan-evidence.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default="CS.LIB",
                         help="library file under toolchain/LIB/ (default CS.LIB, the confirmed small model)")
    parser.add_argument("--apply", action="store_true",
                         help="promote accepted matches into layout/manifest.json")
    parser.add_argument("--min-size", type=int, default=MEMMEM_MIN_SIZE,
                         help="minimum _TEXT size to attempt the memmem fallback path")
    args = parser.parse_args()

    result = scan(args.library, args.min_size)
    print(json.dumps({k: v for k, v in result.items() if k != "rejected_sample"}, indent=2))

    applied = False
    if args.apply and result["accepted"]:
        apply_result = apply_matches(result)
        applied = apply_result["applied"]
        print(f"Applied {len(result['accepted'])} matches; "
              f"manifest now has {apply_result['region_count']} regions.")

    write_evidence(result, applied)


if __name__ == "__main__":
    main()
