"""Slice the unpacked DAVE.EXE image into per-region raw byte extracts.

Reads layout/manifest.json and build/DAVE_unpacked.exe, and writes one file
per region under raw/<id>.bin. This is the bootstrap fallback source for any
region that does not yet have a generator (compiled C/ASM, structured codec,
or asset encoder) — see docs/vision.md's ownership-progression ladder.
"""
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "layout" / "manifest.json"
RAW_DIR = ROOT / "raw"


def load_manifest():
    return json.loads(MANIFEST.read_text())


def main():
    manifest = load_manifest()
    image_path = ROOT / manifest["unpacked_original"]["path"]
    data = image_path.read_bytes()

    expected_size = manifest["unpacked_original"]["size"]
    expected_md5 = manifest["unpacked_original"]["md5"]
    actual_md5 = hashlib.md5(data).hexdigest()
    if len(data) != expected_size or actual_md5 != expected_md5:
        raise SystemExit(
            f"unpacked image mismatch: size {len(data)} (expected {expected_size}), "
            f"md5 {actual_md5} (expected {expected_md5})"
        )

    RAW_DIR.mkdir(exist_ok=True)
    for region in manifest["regions"]:
        chunk = data[region["start"]:region["end"]]
        out_path = RAW_DIR / f"{region['id']}.bin"
        out_path.write_bytes(chunk)
        print(f"{region['id']}: {region['start']:#x}-{region['end']:#x} "
              f"({len(chunk)} bytes) -> {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
