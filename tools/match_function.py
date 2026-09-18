"""Compile-and-compare pipeline for promoting a MATCHING_C region.

Generalizes the "match modulo fixups" proof standard (used by
tools/recover_startup_binding.py for STARTUP_C0S and tools/library_scanner.py
for linked-in runtime routines) to hand-written candidate.c source files that
are claimed to reproduce actual GAME code (not linked library code).

Pipeline: compile candidate.c with the pinned Turbo C++ 1.00 toolchain (via
tools/compile_probe.py's `run()`, so the exact same DOSBox-X harness and
default flags -ms -1- -f- -N are used) -> parse the resulting OMF object
(tools/omf.py) -> take its `_TEXT` segment -> compare byte-for-byte against
the declared target file-offset range in build/DAVE_unpacked.exe -> accept
only if every differing byte is explained by a FIXUPP record declared for
that exact byte offset in the object's `_TEXT` segment (the same bar as
STARTUP_C0S; "unexplained" differences are a hard rejection, not a partial
match).

A function's target range does not have to be the function's *complete*
address range as delineated by some other tool (e.g. docs/function-census.json
may cut a real function's boundary short at a jump table or another quirk);
it only has to be a range this tool independently re-derives byte-for-byte.
The candidate source is free to include placeholder code, so long as (a) the
compiled bytes covering the declared target range are fully explained, and
(b) placeholder code lives entirely outside the declared range (this tool
does not care what happens outside it, but does not silently trim the
declared range to dodge a bad byte either -- the full extent must match).

Usage:
    python tools/match_function.py <candidate.c> <start_hex> <end_hex> \\
        [--model s] [--flags "..."] [--apply --id F_6D64 \\
        --description "..." --src src/F_6D64.c]

Without --apply, only prints the comparison report. With --apply, copies
candidate.c to the given --src path (recorded in the manifest as `source`),
promotes [start,end) in layout/manifest.json to kind="MATCHING_C", and
reruns extract_raw.py + reconstruct.py + the full test suite, restoring the
original manifest/raw state on any failure (same safety discipline as
tools/library_scanner.py's apply_matches).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_probe  # noqa: E402
import omf  # noqa: E402
import reconstruct  # noqa: E402

MANIFEST_PATH = ROOT / "layout" / "manifest.json"
UNPACKED_PATH = ROOT / "build" / "DAVE_unpacked.exe"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def unpacked_bytes() -> bytes:
    manifest = load_manifest()
    data = UNPACKED_PATH.read_bytes()
    expected = manifest["unpacked_original"]
    if len(data) != expected["size"] or hashlib.md5(data).hexdigest() != expected["md5"]:
        raise SystemExit("build/DAVE_unpacked.exe does not match the pinned specimen")
    return data


def compare_modulo_fixups(candidate: bytes, target: bytes, covered: set) -> dict:
    n = len(target)
    if len(candidate) < n:
        raise SystemExit(
            f"compiled _TEXT segment ({len(candidate)} bytes) is shorter than "
            f"the target range ({n} bytes) -- cannot cover the full extent"
        )
    diffs = [i for i in range(n) if candidate[i] != target[i]]
    unexplained = [i for i in diffs if i not in covered]
    return {
        "target_length": n,
        "total_diffs": len(diffs),
        "diff_offsets": diffs,
        "fixup_covered_bytes": len(covered),
        "unexplained_diffs": unexplained,
        "exact_match_modulo_fixups": len(unexplained) == 0,
    }


def run_match(source: pathlib.Path, start: int, end: int, model: str, flags: str) -> dict:
    obj_path = compile_probe.run(source, model, flags)
    obj_bytes = obj_path.read_bytes()
    mod = omf.OmfReader().read(obj_bytes, obj_path.stem)
    text = mod.segment_bytes("_TEXT")

    target = unpacked_bytes()[start:end]
    covered = set()
    for fx in mod.fixups_in("_TEXT"):
        covered.update(range(fx["offset"], fx["offset"] + fx["width"]))

    result = compare_modulo_fixups(text[:end - start], target, covered)
    result.update({
        "source": str(source),
        "start": start,
        "end": end,
        "model": model,
        "flags": flags,
        "object_sha256": hashlib.sha256(obj_bytes).hexdigest(),
        "text_segment_length": len(text),
        "publics": mod.publics,
        "fixups": mod.fixups_in("_TEXT"),
    })
    return result


def apply_promotion(result: dict, region_id: str, description: str,
                     src_dest: pathlib.Path, candidate_source: pathlib.Path):
    if not result["exact_match_modulo_fixups"]:
        raise SystemExit("refusing to promote: match is not exact modulo fixups")

    if not src_dest.is_absolute():
        src_dest = ROOT / src_dest
    if not candidate_source.is_absolute():
        candidate_source = ROOT / candidate_source

    manifest_backup = MANIFEST_PATH.read_text()
    raw_dir = ROOT / "raw"
    raw_backup = {p.name: p.read_bytes() for p in raw_dir.glob("*.bin")}

    src_dest.parent.mkdir(parents=True, exist_ok=True)
    src_existed = src_dest.exists()
    src_backup = src_dest.read_bytes() if src_existed else None
    if src_dest.resolve() != candidate_source.resolve():
        shutil.copyfile(candidate_source, src_dest)

    manifest = load_manifest()
    regions = manifest["regions"]
    start, end = result["start"], result["end"]
    idx = next(
        i for i, r in enumerate(regions)
        if r["kind"] == "RAW_UNKNOWN" and r["start"] <= start and end <= r["end"]
    )
    old = regions[idx]
    new_regions = []
    if old["start"] < start:
        new_regions.append({**old, "end": start, "id": f"{old['id']}_{old['start']:X}_{start:X}"})
    new_regions.append({
        "id": region_id,
        "start": start,
        "end": end,
        "kind": "MATCHING_C",
        "classification": "code",
        "source": str(src_dest.relative_to(ROOT)).replace("\\", "/"),
        "compile_flags": {"model": result["model"], "flags": result["flags"]},
        "object_sha256": result["object_sha256"],
        "description": description,
        "matching_status": "EXACT_MODULO_FIXUPS",
        "matching_status_note": (
            f"tools/match_function.py: compiling "
            f"{str(src_dest.relative_to(ROOT)).replace(chr(92), '/')} "
            f"with the pinned Turbo C++ 1.00 toolchain ({result['model']} model, "
            f"flags {result['flags']!r}) reproduces file offset "
            f"[{start:#x},{end:#x}) with zero unexplained differences "
            f"({result['fixup_covered_bytes']} fixup-covered bytes; fixup "
            "targets -- addresses of externally-resolved symbols/segments -- "
            "are not independently re-derived, matching the same standard "
            "used for STARTUP_C0S and the library_scanner.py promotions)."
        ),
        "artifact": f"raw/{region_id}.bin",
    })
    if end < old["end"]:
        new_regions.append({**old, "start": end, "id": f"{old['id']}_{end:X}_{old['end']:X}"})
    regions[idx:idx + 1] = new_regions
    regions.sort(key=lambda r: r["start"])
    manifest["regions"] = regions

    reconstruct.validate_ownership(manifest)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    def restore():
        MANIFEST_PATH.write_text(manifest_backup)
        for p in raw_dir.glob("*.bin"):
            if p.name not in raw_backup:
                p.unlink()
        for name, content in raw_backup.items():
            (raw_dir / name).write_bytes(content)
        if src_existed:
            src_dest.write_bytes(src_backup)
        else:
            src_dest.unlink(missing_ok=True)

    try:
        extract = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "extract_raw.py")],
            cwd=ROOT, capture_output=True, text=True)
        if extract.returncode != 0:
            raise RuntimeError(f"extract_raw.py failed:\n{extract.stdout}\n{extract.stderr}")
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("start", help="target range start, e.g. 0x6d64")
    parser.add_argument("end", help="target range end, e.g. 0x6d8a")
    parser.add_argument("--model", default="s", choices=list(compile_probe.MODEL_FLAG))
    parser.add_argument("--flags", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--id", dest="region_id", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--src", type=pathlib.Path, default=None,
                         help="destination under src/ to copy the candidate to")
    args = parser.parse_args()

    start = int(args.start, 0)
    end = int(args.end, 0)

    result = run_match(args.source, start, end, args.model, args.flags)
    printable = {k: v for k, v in result.items() if k not in ("fixups",)}
    print(json.dumps(printable, indent=2))

    if args.apply:
        if not (args.region_id and args.description and args.src):
            raise SystemExit("--apply requires --id, --description, and --src")
        apply_result = apply_promotion(result, args.region_id, args.description,
                                        args.src, args.source)
        print(f"Applied; manifest now has {apply_result['region_count']} regions.")


if __name__ == "__main__":
    main()
