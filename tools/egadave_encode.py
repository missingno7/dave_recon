"""Encoder for assets/EGADAVE.DAV: rebuilds the file from the structured decode
produced by tools/egadave_decode.py (build/egadave_decoded/manifest.json + PNGs).

This is the inverse of tools/egadave_decode.py; see that module's docstring for
the full format description. Given the exact same manifest + per-resource pixel
rasters that the decoder produced, this script must reproduce the original
EGADAVE.DAV byte-for-byte (proven by tests/test_egadave_roundtrip.py).

Resources are re-encoded in one of three ways depending on `kind` in the
manifest:
  - FIXED_TILE_16x16 / SPRITE_VAR: pixel indices are read back out of the PNG
    and re-packed into row-planar, MSB-first, 4-plane (I,R,G,B) EGA bytes; for
    SPRITE_VAR a 4-byte little-endian (declared_width, declared_height) header
    is re-emitted first.
  - RAW_UNKNOWN: the original bytes are copied back verbatim from the raw .bin
    fallback file (see the decoder's RAW_UNKNOWN safety net).
"""
import argparse
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import egadave_decode as dec  # noqa: E402


def read_png_indices(path: pathlib.Path, padded_width: int, stored_rows: int):
    from PIL import Image
    img = Image.open(path)
    if img.mode != 'P':
        img = img.convert('P')
    w, h = img.size
    if (w, h) != (padded_width, stored_rows):
        raise ValueError(f"{path}: size {w}x{h} != expected {padded_width}x{stored_rows}")
    data = img.tobytes()
    px = [data[r * padded_width:(r + 1) * padded_width] for r in range(stored_rows)]
    return px


def encode_resource(meta: dict, out_dir: pathlib.Path) -> bytes:
    kind = meta["kind"]
    if kind == "RAW_UNKNOWN":
        return (out_dir / meta["file"]).read_bytes()

    padded_width = meta["padded_width"]
    stored_rows = meta["stored_rows"]
    px = read_png_indices(out_dir / meta["file"], padded_width, stored_rows)
    body = dec.encode_planar(px, padded_width, stored_rows)

    if kind == "FIXED_TILE_16x16":
        return body
    elif kind == "SPRITE_VAR":
        header = struct.pack('<HH', meta["declared_width"], meta["declared_height"])
        return header + body
    else:
        raise ValueError(f"unknown resource kind {kind!r} for resource {meta['index']}")


def encode_file(decoded_dir: pathlib.Path, out_path: pathlib.Path) -> bytes:
    manifest = json.loads((decoded_dir / "manifest.json").read_text())
    resources = manifest["resources"]
    count = manifest["header"]["count"]
    if len(resources) != count:
        raise ValueError(f"manifest has {len(resources)} resources but header count is {count}")

    bodies = [encode_resource(r, decoded_dir) for r in resources]

    table_end = 4 + count * 4
    offsets = []
    cursor = table_end
    for body in bodies:
        offsets.append(cursor)
        cursor += len(body)

    out = bytearray()
    out += struct.pack('<I', count)
    for off in offsets:
        out += struct.pack('<I', off)
    for body in bodies:
        out += body

    out_bytes = bytes(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out_bytes)
    return out_bytes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decoded", default=str(ROOT / "build" / "egadave_decoded"))
    parser.add_argument("--out", default=str(ROOT / "build" / "EGADAVE_rebuilt.DAV"))
    parser.add_argument("--check-against",
                         help="optional path to compare the rebuilt file against byte-for-byte")
    args = parser.parse_args(argv)

    out_bytes = encode_file(pathlib.Path(args.decoded), pathlib.Path(args.out))
    print(f"Encoded {len(out_bytes)} bytes to {args.out} (md5={hashlib.md5(out_bytes).hexdigest()})")

    if args.check_against:
        ref = pathlib.Path(args.check_against).read_bytes()
        if ref == out_bytes:
            print("EXACT MATCH against", args.check_against)
        else:
            print("MISMATCH against", args.check_against, "-", len(ref), "vs", len(out_bytes), "bytes")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
