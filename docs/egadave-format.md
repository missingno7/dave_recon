# EGADAVE.DAV format

Status on the data/asset progression ladder (see `docs/vision.md`):
**REBUILDABLE**, with an **EXACT_MATCH** demonstrated for the whole file:
decoding `assets/EGADAVE.DAV` with `tools/egadave_decode.py` and re-encoding
with `tools/egadave_encode.py` reproduces the original file byte-for-byte
(MD5 `15e4cfe305600a8acd39d4bc7fe9c591`), for all 401 resources, with zero
`RAW_UNKNOWN` fallbacks. See `tests/test_egadave_roundtrip.py` for the proof.

This document records what was independently verified against the actual
specimen bytes. Public prior art (the "Dangerous Dave Tileset Format" page on
ModdingWiki, credited there to Levellass's reverse engineering -
https://moddingwiki.shikadi.net/wiki/Dangerous_Dave_Tileset_Format, and the
general "Raw EGA data" page - https://moddingwiki.shikadi.net/wiki/Raw_EGA_data)
was consulted as a starting point and matched our independent byte-level
findings exactly; every claim below was re-derived and checked against the
actual file, not just copied from that source.

## 1. File header and offset table

```
offset 0        uint32 LE   count               (= 401 in this specimen)
offset 4        uint32 LE[count]  offsets[]      absolute file offsets, one per resource
offset offsets[0] (== 4 + count*4)   resource data begins
```

Verified:
- `count` = 401 (`tools/egadave_decode.py:read_header_and_table`).
- `offsets[]` is strictly increasing over its full 401 entries (no exceptions).
- `offsets[0] == 4 + count*4` exactly (1608 == 1608): the first resource begins
  immediately after the offset table, with no gap or padding.
- Resource `i`'s size is `offsets[i+1] - offsets[i]`, and for the last resource
  (`i == count-1`), `file_size - offsets[i]`. The last resource's computed end
  (`offsets[400] + size(400)`) equals the file size exactly (86332): the table
  + resource data accounts for every byte in the file with no trailing padding.

This 32-bit-count-then-32-bit-offset-table structure was initially suspected to
be a flat "table of N 4-byte offsets where N = offsets[0]/4" (as recorded in
the original `docs/specimen-manifest.json` hypothesis: `0x191/4 = 100.25`).
That arithmetic does not divide evenly, which was the first sign the leading
value is a *count*, not the first entry of a pure offset array. Treating byte 0
as `count` and the table as starting at byte 4 resolves the fractional-entry
problem exactly and is confirmed by `offsets[0] == 4 + count*4`.

## 2. Two resource kinds, told apart purely by size

Walking all 401 resources by their computed `(offset, size)` bounds:

- Resources 0..52 (53 resources) are **all** exactly 128 bytes.
- Resources 53..400 (348 resources) are **never** exactly 128 bytes (sizes
  range from 24 to 2636 bytes).

The boundary is completely clean (verified exhaustively, zero exceptions), so
resource kind can be determined purely from `size == 128` without needing to
know the index ranges as a separate rule.

### 2a. `FIXED_TILE_16x16` (size == 128, indices 0..52)

A 16x16-pixel, 4-bitplane EGA tile with **no header** - the full 128 bytes are
pixel data.

Layout: **row-planar**. For each of the 16 rows, 4 consecutive 16-bit
(2-byte) plane words, one per bitplane, **MSB-first** (bit 15 of the plane
word = the leftmost pixel of the row). `16 rows * 4 planes * 2 bytes = 128
bytes` exactly, matching the originally-observed constant `+0x80` stride
between early offset-table entries.

Confirmed by rendering: decoding under this hypothesis produces coherent,
clearly-intentional tile art (a 3D-bevelled stone/metal block with light-gray
face and dark-gray/white bevel highlights at resource 2; a striped
ladder/pipe-like tile at resource 3; a symmetric diamond/gem shape at resource
16; etc.) - not visual noise. Resource 0 happens to be all-zero (a blank
tile), which is a plausible "empty/background" tile 0 in a level-tile set.

### 2b. `SPRITE_VAR` (size != 128, indices 53..400)

```
offset +0   uint16 LE   declared_width    (pixels)
offset +2   uint16 LE   declared_height   (pixels)
offset +4   ...         pixel data
```

Pixel data layout, same row-planar / MSB-first / 4-plane convention as the
fixed tiles, but with two derived dimensions that differ from the two header
fields:

- `padded_width = ceil(declared_width / 8) * 8` - each plane row is stored as
  a whole number of bytes, so a width not divisible by 8 is padded up to the
  next multiple of 8 (this matches the "widths not divisible by 8 are stored
  as if rounded up" note in the public prior art).
- `stored_rows = declared_height + 1` - **verified with zero exceptions across
  all 348 `SPRITE_VAR` resources**: the actual pixel buffer always has exactly
  one more row than the declared height. The reason for this extra row is not
  yet understood (candidate guesses: a scratch/shift row for the runtime
  blitter, or the height field is a "last row index" rather than a count) but
  the rule itself is exact and required for byte-identical reconstruction.

Data size = `(padded_width/8) * 4 planes * stored_rows` bytes. This formula
was checked against `offsets[i+1]-offsets[i]-4` for all 348 `SPRITE_VAR`
resources with **zero exceptions**.

**Padding columns are not reliably zero.** For sprites whose `declared_width`
isn't a multiple of 8, the extra padding columns (`declared_width` ..
`padded_width-1`) were checked empirically and are frequently non-zero
(roughly 90% of sampled padding bits across padded rows were set). This means
an exact round trip requires preserving the *entire* `padded_width x
stored_rows` raster bit-for-bit, not just the nominally "visible"
`declared_width x declared_height` region. `tools/egadave_decode.py` stores
the full padded raster in each PNG for exactly this reason; `declared_width`/
`declared_height`/`padded_width`/`stored_rows` are all recorded separately in
the manifest so a future consumer can still crop to the semantically-visible
region if desired.

Confirmed by rendering: resources 53-56 (all `declared_width=23,
declared_height=16`) decode to what is recognizably the *same* sprite shifted
one pixel to the right in each successive resource - exactly matching the
public prior art's description of Dangerous Dave storing four
horizontally-shifted EGA copies of each sprite frame (needed because EGA
planar hardware can only address pixels on byte boundaries, so smooth
sub-byte horizontal scrolling requires pre-shifted copies). Resource 57 (same
declared size) decodes to a visibly different pose - consistent with the next
animation frame.

There are 36 distinct `(declared_width, declared_height)` pairs among the 348
`SPRITE_VAR` resources; by far the most common is `(23, 16)` (148 resources -
consistent with 37 four-shifted-copies sprite groups of that one size, though
groups are not always contiguous runs of exactly 4 in the offset table, so
this repo does not yet assert an explicit sprite-frame/animation grouping
structure - only the per-resource pixel format is claimed here).

## 3. Bitplane order, bit order, and palette

- 4 bitplanes, in the order **Intensity, Red, Green, Blue** ("I, R, G, B"),
  matching the public prior art's documented order for this format.
- Bits within each plane word are **MSB-first**: bit `(width-1)` of the plane
  word is the leftmost pixel.
- A pixel's final palette index is `(I<<3) | (R<<2) | (G<<1) | B`, using the
  standard 16-color EGA/CGA palette:

  | idx | name          | RGB (0-255)      |
  |-----|---------------|------------------|
  | 0   | black         | (0, 0, 0)        |
  | 1   | blue          | (0, 0, 170)      |
  | 2   | green         | (0, 170, 0)      |
  | 3   | cyan          | (0, 170, 170)    |
  | 4   | red           | (170, 0, 0)      |
  | 5   | magenta       | (170, 0, 170)    |
  | 6   | brown         | (170, 85, 0)     |
  | 7   | light gray    | (170, 170, 170)  |
  | 8   | dark gray     | (85, 85, 85)     |
  | 9   | light blue    | (85, 85, 255)    |
  | 10  | light green   | (85, 255, 85)    |
  | 11  | light cyan    | (85, 255, 255)   |
  | 12  | light red     | (255, 85, 85)    |
  | 13  | light magenta | (255, 85, 255)   |
  | 14  | yellow        | (255, 255, 85)   |
  | 15  | white         | (255, 255, 255)  |

  This is the standard EGA default-palette mapping where bit weights are
  `Intensity=8, Red=4, Green=2, Blue=1` (e.g. index 8 = intensity bit alone =
  dark gray, index 4 = red bit alone = pure red, etc.) - verified by checking
  that decoding under this exact bit-weight assignment produces recognizable,
  coherent imagery (see above), whereas no other plane ordering was needed
  once this one was tried (the public prior art's documented order matched on
  the first attempt and was independently confirmed, so the "B/G/R/I" and
  other orderings mentioned as generic possibilities in `Raw_EGA_data` were
  not required for this specimen).

## 4. Tooling

- `tools/egadave_decode.py` - parses the header/table, decodes every resource
  (both kinds) into pixel rasters, renders each to a PNG (indexed-color, using
  the palette above) under `build/egadave_decoded/resources/`, and writes
  `build/egadave_decoded/manifest.json` recording each resource's offset,
  size, kind, and format parameters (`declared_width/height`,
  `padded_width`, `stored_rows`, `header_bytes`). Falls back to a raw `.bin`
  copy plus `kind: "RAW_UNKNOWN"` for any resource that doesn't fit the format
  (none do, in this specimen - `raw_fallback_count` is 0).
- `tools/egadave_encode.py` - the inverse: reads the manifest + PNGs (or raw
  `.bin` fallbacks) and re-assembles the exact original file layout (header,
  offset table recomputed from resource sizes, then resource bytes
  concatenated in order).
- `tests/test_egadave_roundtrip.py` - proves the full decode/encode round trip
  is byte-identical to `assets/EGADAVE.DAV` (MD5 match), plus targeted unit
  tests pinning down the offset-table arithmetic and the exact bit/plane
  convention.

Reproduce the round-trip proof:

```sh
python tools/egadave_decode.py
python tools/egadave_encode.py --check-against assets/EGADAVE.DAV
```

See `docs/egadave-format.json` for a machine-readable version of this schema.
