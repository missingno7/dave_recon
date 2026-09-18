# LZEXE 0.91 unpacking

`DAVE.EXE` is packed with LZEXE 0.91 (Fabrice Bellard's EXE compressor,
1990). This document explains the packed-file format, how
`tools/lzexe_unpack.py` reverses it, and what packing-layer information is
preserved vs. discarded -- relevant later if we want to re-derive the exact
packed bytes from the unpacked image.

## 1. The packed file layout

A file produced by LZEXE 0.91 looks like this on disk:

```
+----------------------------+  offset 0
| 32-byte MZ header          |  e_cparhdr = 2 (paragraphs) -> 32 bytes
|   ...                      |  e_crlc = 0, e_lfarlc = 0x1C
|   bytes 0x1C..0x1F = "LZ91"|  (signature, sits where a real header's
+----------------------------+   e_res[0] / start of reloc table would be)
| compressed program data    |  LZ77-compressed code+data, length given
|   (LZ77 stream)             |  by the "info block" below (in paragraphs)
+----------------------------+
| decompression stub code    |  a small real-mode program: decompresses
|  info block (16 bytes)     |  the data above, in place, into low memory,
|  ... stub instructions ... |  rebuilds the real relocation table, fixes
|  compressed reloc table    |  up CS/SS, and jumps to the real entry point
+----------------------------+
```

The outer MZ header is deliberately minimal and "wrong" on purpose: `e_ip`/
`e_cs` point at the decompression stub (not the game), `e_crlc` is 0 so DOS
performs no relocation fixups at load time (the stub does its own), and the
4 bytes at file offset 0x1C -- which a real MZ header doesn't define (that
address is `e_lfarlc`, the start of a relocation table, and none exists
here) -- are repurposed to hold the ASCII marker `"LZ91"` (`"LZ09"` for the
older 0.90 packer).

### The "info block"

The decompression stub begins with a 16-byte info block at its own CS:0000
(the stub's own code starts right after it, at CS:000E, which is exactly
where the outer header's `e_ip` points):

| Offset | Field | Meaning |
|--------|-------|---------|
| 0x00 | real IP | entry point offset into the decompressed load module |
| 0x02 | real CS | entry point segment, relative to the load module base |
| 0x04 | real SP | stack pointer to set before jumping to the real entry point |
| 0x06 | real SS | stack segment, relative to the load module base |
| 0x08 | compressed size | size of the LZ77 stream, in paragraphs |
| 0x0A | extra paragraphs | extra memory the packer's stub needed at runtime |
| 0x0C | stub+reloc size | size of the stub code + compressed reloc table, in bytes |
| 0x0E | checksum | only meaningful for 0.90; unused by our decompressor |

From this, `stub_base = (e_cparhdr + e_cs_packed) * 16` locates the info
block in the file, `stub_base - compressed_size*16` locates the start of
the LZ77 stream (which is always immediately after the 32-byte header, i.e.
file offset 0x20), and for version 0.91 specifically the compressed
relocation table always starts at `stub_base + 0x158` (0.90 uses a
different, simpler encoding at `stub_base + 0x19D` -- not implemented here
since this file is confirmed 0.91 via the `LZ91` marker).

## 2. The LZ77 compressed stream

The stream is a sequence of 16-bit little-endian "tag" words interleaved
with literal/match data, read from the same byte cursor. A tag word's bits
are consumed LSB-first, one at a time; when 16 bits have been used up, a
fresh tag word is read (see `BitReader` in the tool).

Per tag bit, the token grammar is:

- **`1`** -- literal byte follows verbatim in the stream.
- **`0 0 LL`** -- short match: `LL` (2 bits, values 0-3) gives
  `length = LL + 2` (2..5), followed by one byte giving the back-reference
  distance as `-(0x100 - byte)`, i.e. -1..-256.
- **`0 1`** -- long match: two following bytes `b1, b2` encode
  `distance = b1 | ((b2 & 0xF8) << 5) | 0xE000` (interpreted as a signed
  16-bit value, giving -1..-8192) and `length = (b2 & 0x07) + 2`. If that
  length works out to exactly 2 (i.e. the low 3 bits of `b2` were 0), a
  further byte is read and reinterpreted:
  - `0` -- end of the compressed stream (decompression is complete);
  - `1` -- an internal "segment normalization" marker the original 16-bit
    real-mode decompressor needed to renormalize its ES:DI/DS:SI pointers
    across a 64K segment boundary. It carries no data and is a no-op for a
    flat output buffer, so this tool just skips it;
  - anything else (`n >= 2`) -- an extended length of `n + 1` (3..256).

Matches are copied **byte by byte**, not with a bulk slice, because LZEXE
allows the source region of a match to overlap the destination (distance
smaller than length) -- that's how runs of a repeated byte or short pattern
are encoded compactly. `decompress_payload` relies on Python's negative
indexing (`out[distance]` with `distance < 0`) to express "N bytes back
from the current end of output", which is exactly the effect of the
original decompressor's `*(p + (int16_t) span)`.

## 3. The compressed relocation table (0.91 encoding)

LZEXE's own relocation fixups (for the *packed* stub) are suppressed
(`e_crlc = 0`); the table that matters is the *original program's*
relocation table, which the packer compressed and tucked inside the stub.
It is decoded as a sequence of deltas from a running linear address,
accumulated into a `(segment, offset)` pair normalized so `offset < 0x10`:

- a nonzero byte `1..255` is a delta, added directly;
- a zero byte introduces a 16-bit word:
  - `0x0000` -- add `0xFFF` paragraphs to the segment accumulator and keep
    reading deltas (this is how the format reaches gaps bigger than 255
    without a dedicated wide-delta encoding -- it repeats near-64K segment
    jumps until the remaining small delta can be expressed in one byte);
  - `0x0001` -- end of table;
  - any other word -- used directly as the delta.

After each delta is added to a running `offset` accumulator, the excess
above 4 bits is folded into the segment (`segment += offset >> 4;
offset &= 0x0F`), producing one final `(offset, segment)` relocation entry.

This decoded table becomes the *real* MZ relocation table in the output:
it is written starting at file offset 0x1C (i.e. `e_lfarlc = 0x1C`,
overlapping exactly where the packed file's `"LZ91"` marker used to be),
padded with zero bytes up to the next 512-byte boundary, and `e_cparhdr` is
set to that padded size in paragraphs.

## 4. Header field reconstruction

- `e_ip`, `e_cs`, `e_sp`, `e_ss` are copied straight from the info block
  (they are already expressed relative to the load module base, exactly
  how MZ headers define them -- no adjustment needed).
- `e_crlc` = number of decoded relocation entries; `e_lfarlc = 0x1C`.
- `e_cparhdr` = reconstructed header size (28 bytes of fixed fields +
  relocation table, padded to a 512-byte boundary) in paragraphs.
- `e_cblp`/`e_cp` are recomputed from the final total file size using the
  standard MZ convention (`e_cblp` = bytes used in the last 512-byte page,
  0 if the file is an exact multiple of 512).
- `e_minalloc`/`e_maxalloc`: LZEXE inflates these in the packed file to
  cover the decompressor's own transient working memory. The original
  values are recovered by subtracting `extra_paragraphs +
  ceil(stub_size_bytes / 16) + 9` from both (skipping `e_maxalloc` if it
  was the "no extra needed" sentinel `0`, and leaving it unadjusted if it
  was the "as much as available" sentinel `0xFFFF`).

## 5. What's preserved vs. discarded (relevant for re-packing later)

**Preserved in the unpacked image** (and therefore recoverable losslessly):
the exact decompressed code+data bytes, the real entry point and stack
registers, and a semantically-correct relocation table (as `(segment,
offset)` pairs, fully expanded -- not in the packer's delta-compressed
form).

**Discarded / not reconstructible from the unpacked image alone:**
- The **decompression stub's own machine code** (the ~470-byte 0.91
  decompressor program itself, which differs slightly release to release
  and was only used to compare against a known signature during analysis;
  it is not needed to produce the decompressed program and this tool does
  not retain it).
- The **exact relocation-table delta encoding choices** the original LZEXE
  packer made. The decode is unambiguous (each byte/word sequence maps to
  exactly one set of deltas), but the reverse direction is not: an encoder
  choosing how to break a large gap into `0xFFF`-paragraph segment jumps
  plus a final small delta has some freedom (e.g. exactly how many
  `0x0000` segment-jump words to emit before the final delta, when more
  than one accumulated small delta could combine into a single jump
  differently). Our tool only performs the forward (decode) direction, so
  it does not need to make -- and does not record -- those choices. A
  future re-packer would need to either replicate LZEXE 0.91's own
  reference encoder behavior byte-for-byte, or simply accept a
  functionally equivalent but not byte-identical relocation table encoding.
- The **LZ77 compression parse** (which match lengths/distances the
  original encoder chose over alternatives) is similarly a one-way street:
  decompression is exact and unambiguous, but re-compressing the plain
  image would require reimplementing (or matching the exact greedy/lazy
  matching heuristics of) LZEXE 0.91's own compressor to get byte-identical
  packed output; a "just correct" LZ77 encoder will typically produce a
  smaller or differently-shaped, but not byte-identical, compressed stream.
- The **extra memory sizing fields** in the info block (`extra_paragraphs`,
  `stub_size_bytes`) are read only to reverse the `e_minalloc`/`e_maxalloc`
  inflation; their packed values depended on the specific stub build and
  are not otherwise meaningful for the decompressed program.

In short: everything needed to *run* or *analyze* the original game (code,
data, entry point, relocations) is fully and exactly recovered. Producing
an LZEXE-0.91-compatible *re-packed* file that is byte-identical to
`DAVE.EXE` would additionally require re-implementing LZEXE's own encoder
(compression heuristics + relocation delta-encoding heuristics + stub
selection), which this tool deliberately does not attempt.

## 6. Verification performed

- Output starts with a valid `MZ` header.
- `e_cp`/`e_cblp`-declared image size exactly equals the produced file's
  actual size (172,848 bytes).
- All 27 reconstructed relocation entries point within the bounds of the
  decompressed load module; `e_crlc` (27) matches the table length and
  `e_lfarlc` (0x1C) points at the real table.
- The real entry point (`e_cs:e_ip` = `0000:0000`, i.e. the very first byte
  of the load module) disassembles as plausible 8086 startup code:
  `BA 4D 25` (`mov dx, 254Dh`), `2E 89 16 35 02` (`mov cs:[0235h], dx`),
  `B4 30` (`mov ah, 30h`), `CD 21` (`int 21h`, DOS "get DOS version" --
  a very characteristic Turbo/Borland-style startup sequence), followed by
  further segment-register setup (`mov bp,[...]`, `mov bx,[...]`, `mov
  ds,...`, `mov es,...`) -- not garbage.
- `e_minalloc` = 1332 paragraphs (~21 KB) and `e_maxalloc` = 0xFFFF ("as
  much memory as available") are plausible for a ~172 KB DOS game.
- **Independent byte-exact confirmation:** the Internet Archive item
  "Dangerous Dave (LZW decompressed)" documents the UNLZEXE-decompressed
  `DAVE.EXE` as 172,848 bytes with SHA1 `9e572f0320ca759bea8f24a0ebcfcb1b68474e13`,
  and the original packed file as 76,586 bytes with SHA1
  `a8e14979d4259bc086b7d6b8ced575c66c4f9fef`. Our input `DAVE.EXE` hashes to
  that exact packed SHA1 (confirming it's the same specimen), and our
  decompressor's output hashes to that exact decompressed SHA1 -- a
  **byte-for-byte match** with an independently produced reference.
