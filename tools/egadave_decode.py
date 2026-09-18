"""Decoder for assets/EGADAVE.DAV, Dangerous Dave's external EGA graphics resource file.

Format (empirically verified against assets/EGADAVE.DAV, cross-checked against the
public "Dangerous Dave Tileset Format" documentation on ModdingWiki -
https://moddingwiki.shikadi.net/wiki/Dangerous_Dave_Tileset_Format - which credits
Levellass for the original reverse engineering):

  offset 0            uint32 LE  `count`  - number of resources (401 in our specimen)
  offset 4            uint32 LE[count]    - `count` absolute file offsets, one per
                                             resource, strictly increasing; offsets[0]
                                             always equals the end of this table
                                             (4 + count*4)
  offset offsets[i]   resource i's bytes; resource i's size is
                                             offsets[i+1]-offsets[i] (or, for the last
                                             resource, file_size-offsets[i])

Two resource kinds, distinguished purely by size (verified: every resource with
size==128 is a fixed tile and none of the 348 non-128-sized resources round-trip
under the fixed-tile interpretation; the boundary is clean: indices 0..52 are all
size 128, indices 53.. are never size 128):

  FIXED_TILE_16x16 (size == 128, no header):
      16x16 pixel, 4-bitplane EGA tile. Row-planar: for each of 16 rows, 4
      consecutive 2-byte (16-bit) plane words, MSB-first (bit 15 = leftmost pixel).
      16 rows * 4 planes * 2 bytes/plane = 128 bytes exactly.

  SPRITE_VAR (size != 128):
      4-byte header: uint16 LE declared_width (pixels), uint16 LE declared_height
      (pixels), followed by pixel data.
      Pixel data uses a padded width rounded up to the next multiple of 8
      (padded_width = ceil(declared_width/8)*8) and, empirically, ALWAYS one more
      row than declared_height (stored_rows = declared_height + 1; verified with
      zero exceptions across all 348 variable resources in the specimen - the
      reason for the extra row is not yet understood, but the rule is exact).
      Row-planar, same MSB-first bit order and 4-plane order as fixed tiles.
      Data size = (padded_width/8) * 4 planes * stored_rows bytes, which matches
      offsets[i+1]-offsets[i]-4 exactly for every one of the 348 variable
      resources with zero exceptions.
      IMPORTANT: the padding columns (declared_width..padded_width-1) are NOT
      reliably zero in the original file (verified empirically - about 90% of
      sampled padding bits are set), so they must be preserved bit-for-bit for an
      exact round trip. This decoder stores the FULL padded_width x stored_rows
      raster (not just the declared visible width/height) so no information is
      lost.

Bitplane order and palette (verified by rendering: produces coherent, symmetric,
tile-like/sprite-like imagery, e.g. a 3D-bevelled block tile, a diamond/gem tile,
and four horizontally-shifted copies of what looks like a game character sprite
at resource indices 53-56 - consistent with ModdingWiki's note that Dangerous
Dave stores 4 horizontally-shifted EGA copies of each sprite frame):

  4 planes, MSB-first, in order Intensity, Red, Green, Blue (matches ModdingWiki's
  documented "I, R, G, B" order for this format).
  Palette index for a pixel = (I<<3) | (R<<2) | (G<<1) | B, using the standard
  16-color EGA/CGA palette (see PALETTE below).

See docs/egadave-format.md and docs/egadave-format.json for the full writeup.
"""
import argparse
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Standard 16-color EGA/CGA palette, indexed by (I<<3)|(R<<2)|(G<<1)|B.
PALETTE = [
    (0x00, 0x00, 0x00),  # 0  black
    (0x00, 0x00, 0xAA),  # 1  blue
    (0x00, 0xAA, 0x00),  # 2  green
    (0x00, 0xAA, 0xAA),  # 3  cyan
    (0xAA, 0x00, 0x00),  # 4  red
    (0xAA, 0x00, 0xAA),  # 5  magenta
    (0xAA, 0x55, 0x00),  # 6  brown
    (0xAA, 0xAA, 0xAA),  # 7  light gray
    (0x55, 0x55, 0x55),  # 8  dark gray
    (0x55, 0x55, 0xFF),  # 9  light blue
    (0x55, 0xFF, 0x55),  # 10 light green
    (0x55, 0xFF, 0xFF),  # 11 light cyan
    (0xFF, 0x55, 0x55),  # 12 light red
    (0xFF, 0x55, 0xFF),  # 13 light magenta
    (0xFF, 0xFF, 0x55),  # 14 yellow
    (0xFF, 0xFF, 0xFF),  # 15 white
]

FIXED_TILE_SIZE = 128
FIXED_TILE_WIDTH = 16
FIXED_TILE_HEIGHT = 16
PLANES = 4


def flat_palette():
    flat = []
    for c in PALETTE:
        flat.extend(c)
    flat.extend([0, 0, 0] * (256 - len(PALETTE)))
    return flat


def read_header_and_table(data: bytes):
    """Parse the uint32 count + offset table. Returns (count, offsets)."""
    count = struct.unpack_from('<I', data, 0)[0]
    offsets = list(struct.unpack_from('<%dI' % count, data, 4))
    table_end = 4 + count * 4
    if offsets[0] != table_end:
        raise ValueError(
            f"offset table end mismatch: offsets[0]={offsets[0]:#x} != "
            f"computed table_end={table_end:#x}"
        )
    for i in range(1, count):
        if offsets[i] <= offsets[i - 1]:
            raise ValueError(f"offset table not strictly increasing at index {i}")
    return count, offsets


def resource_bounds(offsets, count, filesize):
    bounds = []
    for i in range(count):
        start = offsets[i]
        end = offsets[i + 1] if i + 1 < count else filesize
        bounds.append((start, end))
    return bounds


def decode_planar(chunk: bytes, padded_width: int, rows: int, planes: int = PLANES):
    """Decode row-planar, MSB-first EGA planar pixel data into a 2D index array."""
    bpr = padded_width // 8
    expected_len = bpr * planes * rows
    if len(chunk) != expected_len:
        raise ValueError(f"chunk length {len(chunk)} != expected {expected_len}")
    px = [[0] * padded_width for _ in range(rows)]
    pos = 0
    for row in range(rows):
        planevals = []
        for _p in range(planes):
            val = 0
            for _b in range(bpr):
                val = (val << 8) | chunk[pos]
                pos += 1
            planevals.append(val)
        for x in range(padded_width):
            bit = padded_width - 1 - x
            idx = 0
            for p in range(planes):
                idx |= ((planevals[p] >> bit) & 1) << (planes - 1 - p)
            px[row][x] = idx
    assert pos == len(chunk)
    return px


def encode_planar(px, padded_width: int, rows: int, planes: int = PLANES) -> bytes:
    """Inverse of decode_planar: 2D index array -> row-planar MSB-first bytes."""
    bpr = padded_width // 8
    out = bytearray()
    for row in range(rows):
        planevals = [0] * planes
        rowpx = px[row]
        for x in range(padded_width):
            idx = rowpx[x]
            bit = padded_width - 1 - x
            for p in range(planes):
                if (idx >> (planes - 1 - p)) & 1:
                    planevals[p] |= (1 << bit)
        for p in range(planes):
            val = planevals[p]
            for b in range(bpr - 1, -1, -1):
                out.append((val >> (b * 8)) & 0xFF)
    return bytes(out)


def decode_resource(data: bytes, index: int, start: int, end: int):
    size = end - start
    if size == FIXED_TILE_SIZE:
        kind = "FIXED_TILE_16x16"
        declared_width = declared_height = 16
        padded_width = FIXED_TILE_WIDTH
        stored_rows = FIXED_TILE_HEIGHT
        header_bytes = 0
        chunk = data[start:end]
    else:
        declared_width, declared_height = struct.unpack_from('<HH', data, start)
        header_bytes = 4
        padded_width = ((declared_width + 7) // 8) * 8
        stored_rows = declared_height + 1
        kind = "SPRITE_VAR"
        chunk = data[start + header_bytes:end]

    px = decode_planar(chunk, padded_width, stored_rows)
    meta = {
        "index": index,
        "offset": start,
        "size": size,
        "kind": kind,
        "declared_width": declared_width,
        "declared_height": declared_height,
        "padded_width": padded_width,
        "stored_rows": stored_rows,
        "header_bytes": header_bytes,
    }
    return meta, px


def write_png(px, padded_width: int, stored_rows: int, path: pathlib.Path):
    from PIL import Image
    img = Image.new('P', (padded_width, stored_rows))
    img.putpalette(flat_palette())
    flat_px = [v for row in px for v in row]
    img.putdata(flat_px)
    img.save(path)


def decode_file(dav_path: pathlib.Path, out_dir: pathlib.Path, write_images: bool = True):
    data = dav_path.read_bytes()
    count, offsets = read_header_and_table(data)
    bounds = resource_bounds(offsets, count, len(data))

    resources_dir = out_dir / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    resources = []
    raw_fallback_count = 0
    for i, (start, end) in enumerate(bounds):
        try:
            meta, px = decode_resource(data, i, start, end)
        except Exception as exc:  # pragma: no cover - safety net, not hit on our specimen
            # RAW_UNKNOWN fallback per project philosophy: never silently guess,
            # keep the exact original bytes recoverable.
            raw_fallback_count += 1
            raw_name = f"res_{i:04d}_raw.bin"
            (resources_dir / raw_name).write_bytes(data[start:end])
            resources.append({
                "index": i,
                "offset": start,
                "size": end - start,
                "kind": "RAW_UNKNOWN",
                "error": str(exc),
                "file": f"resources/{raw_name}",
            })
            continue

        if meta["kind"] == "FIXED_TILE_16x16":
            name = f"res_{i:04d}_tile.png"
        else:
            name = f"res_{i:04d}_sprite.png"
        if write_images:
            write_png(px, meta["padded_width"], meta["stored_rows"], resources_dir / name)
        meta["file"] = f"resources/{name}"
        resources.append(meta)

    manifest = {
        "format": "egadave-decoded-v1",
        "source": {
            "path": "assets/EGADAVE.DAV",
            "size": len(data),
            "md5": hashlib.md5(data).hexdigest(),
        },
        "header": {"count": count},
        "table": {
            "start": 0,
            "entries_start": 4,
            "entry_count": count,
            "table_end": 4 + count * 4,
        },
        "palette": {
            "description": "standard 16-color EGA/CGA palette, index=(I<<3)|(R<<2)|(G<<1)|B",
            "colors_rgb": PALETTE,
        },
        "plane_order": ["I", "R", "G", "B"],
        "bit_order": "MSB_FIRST",
        "raw_fallback_count": raw_fallback_count,
        "resources": resources,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dav", default=str(ROOT / "assets" / "EGADAVE.DAV"))
    parser.add_argument("--out", default=str(ROOT / "build" / "egadave_decoded"))
    parser.add_argument("--no-images", action="store_true",
                         help="skip writing PNGs, only write manifest.json (faster)")
    args = parser.parse_args(argv)

    manifest = decode_file(pathlib.Path(args.dav), pathlib.Path(args.out),
                            write_images=not args.no_images)
    print(f"Decoded {len(manifest['resources'])} resources "
          f"({manifest['raw_fallback_count']} raw fallback) to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
