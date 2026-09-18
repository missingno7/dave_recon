"""Validate layout/manifest.json and rebuild the unpacked DAVE.EXE image from it.

This is the bootstrap reconstruction builder. Every region currently reads
its bytes from raw/<id>.bin (a literal fallback extract) rather than from a
generator (compiled C/ASM, structured codec, asset encoder). As regions are
promoted (see docs/vision.md's ownership ladder), this script should grow a
per-kind dispatch that prefers the region's real source over its raw
fallback, and MATCHING_C/MATCHING_ASM/KNOWN_LIBRARY/STRUCTURED_* regions
should fail loudly if their generator's output does not match the stored
raw extract exactly.

Usage: python tools/reconstruct.py [--report build/report.json]
"""
import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "layout" / "manifest.json"
RAW_DIR = ROOT / "raw"

VALID_KINDS = {
    "MZ_HEADER",
    "RELOCATION_TABLE",
    "MATCHING_C",
    "MATCHING_ASM",
    "KNOWN_LIBRARY",
    "STRUCTURED_DATA",
    "STRUCTURED_ASSET",
    "PADDING",
    "RAW_UNKNOWN",
}


def load_manifest():
    manifest = json.loads(MANIFEST.read_text())
    if manifest["format"] != "dave-owned-exe-v1":
        raise SystemExit(f"unexpected manifest format {manifest['format']!r}")
    return manifest


def validate_ownership(manifest):
    """Every byte of the unpacked image must have exactly one owner."""
    regions = sorted(manifest["regions"], key=lambda r: r["start"])
    total_size = manifest["unpacked_original"]["size"]

    seen_ids = set()
    cursor = 0
    for region in regions:
        rid, start, end, kind = region["id"], region["start"], region["end"], region["kind"]
        if rid in seen_ids:
            raise SystemExit(f"duplicate region id {rid!r}")
        seen_ids.add(rid)
        if kind not in VALID_KINDS:
            raise SystemExit(f"region {rid!r} has invalid kind {kind!r}")
        if end <= start:
            raise SystemExit(f"region {rid!r} has non-positive extent [{start},{end})")
        if start != cursor:
            if start > cursor:
                raise SystemExit(f"ownership gap before region {rid!r}: bytes [{cursor:#x},{start:#x}) are unowned")
            raise SystemExit(f"ownership overlap: region {rid!r} starts at {start:#x} but cursor is at {cursor:#x}")
        cursor = end
    if cursor != total_size:
        raise SystemExit(f"ownership does not cover full image: covered up to {cursor:#x}, image is {total_size:#x}")
    if regions[0]["kind"] != "MZ_HEADER" or regions[0]["start"] != 0:
        raise SystemExit("first region must be MZ_HEADER starting at offset 0")
    return regions


def region_bytes(region):
    # Bootstrap: every region currently reads its literal raw extract.
    # TODO(promotion): dispatch on region["kind"] to prefer a real generator
    # (compiled C/ASM object, structured codec, asset encoder) once one
    # exists for a given region, and treat this raw read as a fallback only.
    raw_path = RAW_DIR / f"{region['id']}.bin"
    if not raw_path.exists():
        raise SystemExit(f"missing raw extract for region {region['id']!r}: {raw_path} "
                          f"(run tools/extract_raw.py first)")
    data = raw_path.read_bytes()
    expected_len = region["end"] - region["start"]
    if len(data) != expected_len:
        raise SystemExit(f"region {region['id']!r} raw extract is {len(data)} bytes, "
                          f"manifest declares {expected_len}")
    return data


def reconstruct(manifest):
    regions = validate_ownership(manifest)
    pieces = [region_bytes(r) for r in regions]
    return b"".join(pieces), regions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=None, help="write a JSON report to this path")
    args = parser.parse_args()

    manifest = load_manifest()
    image, regions = reconstruct(manifest)

    expected_size = manifest["unpacked_original"]["size"]
    expected_md5 = manifest["unpacked_original"]["md5"]
    actual_md5 = hashlib.md5(image).hexdigest()

    ok = len(image) == expected_size and actual_md5 == expected_md5

    counts = {}
    for r in regions:
        n = r["end"] - r["start"]
        counts[r["kind"]] = counts.get(r["kind"], 0) + n

    report = {
        "ok": ok,
        "reconstructed_size": len(image),
        "expected_size": expected_size,
        "reconstructed_md5": actual_md5,
        "expected_md5": expected_md5,
        "region_count": len(regions),
        "bytes_by_kind": counts,
    }

    print(json.dumps(report, indent=2))
    if args.report:
        pathlib.Path(args.report).write_text(json.dumps(report, indent=2))

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
