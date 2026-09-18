#!/usr/bin/env python3
"""
lzexe_unpack.py -- from-scratch LZEXE 0.91 decompressor.

Reconstructs an original DOS MZ executable from an LZEXE 0.91 - compressed
one. Written from a careful study of the LZEXE 0.91 packed-file layout and
its LZ77-style compression scheme (see docs/lzexe-unpacking.md for the full
writeup of how the format works and what this tool does with each part).

Usage:
    python lzexe_unpack.py <packed.exe> <output_unpacked.exe>
"""

import struct
import sys

MZ_HEADER_WORDS = 16          # a "minimal" (e_cparhdr=2) MZ header is 16 words / 32 bytes
INFO_BLOCK_OFFSET = 0x00      # the real-header "info block" sits at CS:0000 of the stub
RELOC_TABLE_OFFSET_V91 = 0x158  # compressed relocation table sits at CS:0158 for v0.91


class LzexeFormatError(Exception):
    pass


# --------------------------------------------------------------------------
# Low level cursor over the packed file's bytes
# --------------------------------------------------------------------------

class ByteCursor:
    """Sequential little-endian reader over an immutable bytes buffer."""

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def u8(self) -> int:
        b = self.data[self.pos]
        self.pos += 1
        return b

    def u16(self) -> int:
        lo = self.data[self.pos]
        hi = self.data[self.pos + 1]
        self.pos += 2
        return lo | (hi << 8)


class BitReader:
    """
    LZEXE's bit-oriented "tag" stream: a 16-bit little-endian word is read
    from the compressed stream, and its bits are consumed LSB-first, one
    per call. When 16 bits have been consumed, a fresh word is read (it
    replaces the buffer outright rather than being merged with leftovers).
    Bit reads and literal/length byte reads share the same underlying
    cursor and interleave in exactly the order the encoder produced them.
    """

    def __init__(self, cursor: ByteCursor):
        self.cursor = cursor
        self.buf = cursor.u16()
        self.count = 16

    def get(self) -> int:
        bit = self.buf & 1
        self.count -= 1
        if self.count == 0:
            self.buf = self.cursor.u16()
            self.count = 16
        else:
            self.buf >>= 1
        return bit


# --------------------------------------------------------------------------
# MZ header parsing
# --------------------------------------------------------------------------

def parse_mz_header(data: bytes):
    """Return the 16 little-endian words of the (minimal, 32-byte) MZ header."""
    if len(data) < 32:
        raise LzexeFormatError("file too short for an MZ header")
    words = list(struct.unpack("<16H", data[0:32]))
    magic = data[0:2]
    if magic not in (b"MZ", b"ZM"):
        raise LzexeFormatError("not an MZ executable")
    return words


def is_lzexe91(data: bytes, header) -> bool:
    e_lfarlc = header[0x0C]
    e_ovno = header[0x0D]
    if e_ovno != 0 or e_lfarlc != 0x1C:
        return False
    return data[0x1C:0x20] == b"LZ91"


# --------------------------------------------------------------------------
# Relocation table decoding (LZEXE 0.91 encoding)
# --------------------------------------------------------------------------

def decode_relocation_table(data: bytes, table_offset: int):
    """
    Decode the LZEXE 0.91 compressed relocation table into a list of
    (offset, segment) pairs, segment/offset already normalized the way a
    real MZ relocation table expects (offset < 0x10, remaining distance
    folded into segment).

    Encoding, one entry at a time, as a delta from the previous entry's
    linear address:
      - a nonzero byte 1..255 is the delta itself;
      - a zero byte introduces a 16-bit word:
          0x0000 -> no relocation here; advance the segment accumulator by
                    0xFFF paragraphs (0xFFF0 bytes) and keep reading deltas
                    (this is how the format reaches deltas > 255 without a
                    dedicated multi-byte delta encoding: it repeatedly
                    "jumps" a near-64K segment stride);
          0x0001 -> end of table;
          anything else -> that word itself is the delta.
    """
    cursor = ByteCursor(data, table_offset)
    rel_off = 0
    rel_seg = 0
    relocations = []
    while True:
        delta = cursor.u8()
        if delta == 0:
            delta = cursor.u16()
            if delta == 0:
                rel_seg = (rel_seg + 0x0FFF) & 0xFFFF
                continue
            if delta == 1:
                break
        rel_off = (rel_off + delta) & 0xFFFF
        rel_seg = (rel_seg + (rel_off >> 4)) & 0xFFFF
        rel_off &= 0x0F
        relocations.append((rel_off, rel_seg))
    return relocations


# --------------------------------------------------------------------------
# LZ77 payload decompression
# --------------------------------------------------------------------------

def decompress_payload(data: bytes, start_offset: int) -> bytes:
    """
    Decode the LZEXE LZ77 stream starting at `start_offset` into the flat
    decompressed program image.

    Token grammar, one "tag" bit at a time (see BitReader):
      1                       -> literal byte follows
      0 0 <ll><ll>            -> short match: 2-bit length code (len = code+2,
                                  i.e. 2..5), 1 byte encodes distance -1..-256
      0 1                     -> long match: 2 bytes encode both distance
                                  (-1..-8192) and a length code; a length
                                  code of 0 means a third byte follows that
                                  either ends the stream (0), signals an
                                  internal segment-normalization no-op (1,
                                  irrelevant to a flat decoded buffer), or
                                  gives an extended length (byte+1, so 3..256)

    Matches copy byte-by-byte (not via slicing) because LZEXE matches are
    allowed to overlap their own source region -- that is how runs of a
    repeated byte (or short repeating pattern) are encoded compactly.
    """
    cursor = ByteCursor(data, start_offset)
    bits = BitReader(cursor)
    out = bytearray()

    while True:
        if bits.get():
            out.append(cursor.u8())
            continue

        if bits.get() == 0:
            length = (bits.get() << 1) | bits.get()
            length += 2
            distance = cursor.u8() | 0xFF00
        else:
            b1 = cursor.u8()
            b2 = cursor.u8()
            distance = b1 | ((b2 & 0xF8) << 5) | 0xE000
            length = (b2 & 0x07) + 2
            if length == 2:
                extra = cursor.u8()
                if extra == 0:
                    break  # end-of-stream marker
                if extra == 1:
                    continue  # segment-normalization no-op, no bytes produced
                length = extra + 1

        if distance >= 0x8000:
            distance -= 0x10000
        for _ in range(length):
            out.append(out[distance])

    return bytes(out)


# --------------------------------------------------------------------------
# Top level unpacking
# --------------------------------------------------------------------------

def unpack(data: bytes) -> bytes:
    header = parse_mz_header(data)
    if not is_lzexe91(data, header):
        raise LzexeFormatError("not an LZEXE 0.91 file (missing LZ91 signature)")

    e_cparhdr = header[0x04]
    e_cs_packed = header[0x0B]

    # File offset of the decompression stub's CS:0000 -- this is also where
    # the "info block" with the real header fields lives.
    stub_base = (e_cparhdr + e_cs_packed) << 4

    info = struct.unpack("<8H", data[stub_base:stub_base + 16])
    real_ip, real_cs, real_sp, real_ss, compressed_paras, extra_paras, stub_size_bytes, _checksum = info

    compressed_data_offset = stub_base - (compressed_paras << 4)
    reloc_table_offset = stub_base + RELOC_TABLE_OFFSET_V91

    relocations = decode_relocation_table(data, reloc_table_offset)
    decompressed = decompress_payload(data, compressed_data_offset)

    # --- Build the reconstructed relocation table + header ---
    reloc_bytes = b"".join(struct.pack("<HH", off, seg) for off, seg in relocations)
    header_len_before_pad = 0x1C + len(reloc_bytes)
    pad = (-header_len_before_pad) % 512
    header_len = header_len_before_pad + pad
    e_cparhdr_new = header_len // 16

    total_size = header_len + len(decompressed)
    e_cblp = total_size & 0x1FF
    e_cp = (total_size + 0x1FF) >> 9

    # e_minalloc/e_maxalloc: LZEXE inflates minalloc (and maxalloc, unless it
    # was the sentinel values 0 or 0xFFFF) to cover the decompressor's own
    # working memory; undo that inflation to recover the original values.
    packed_minalloc = header[0x05]
    packed_maxalloc = header[0x06]
    new_minalloc = packed_minalloc
    new_maxalloc = packed_maxalloc
    if packed_maxalloc != 0:
        adjustment = extra_paras + ((stub_size_bytes + 15) >> 4) + 9
        new_minalloc = (packed_minalloc - adjustment) & 0xFFFF
        if packed_maxalloc != 0xFFFF:
            new_maxalloc = (packed_maxalloc - (packed_minalloc - new_minalloc)) & 0xFFFF

    out_header = list(header)
    out_header[0x01] = e_cblp
    out_header[0x02] = e_cp
    out_header[0x03] = len(relocations)          # e_crlc
    out_header[0x04] = e_cparhdr_new              # e_cparhdr
    out_header[0x05] = new_minalloc
    out_header[0x06] = new_maxalloc
    out_header[0x07] = real_ss
    out_header[0x08] = real_sp
    out_header[0x0A] = real_ip
    out_header[0x0B] = real_cs
    out_header[0x0C] = 0x1C                       # e_lfarlc: reloc table right after fixed header
    out_header[0x0D] = 0                          # e_ovno

    # Only the 14 defined header words (28 bytes, e_magic..e_ovno) precede
    # the relocation table -- the packed file's trailing 4 header bytes
    # (0x1C..0x1F) held the "LZ91" signature instead of real header fields
    # and are not part of the reconstructed header at all; the relocation
    # table starts right there, at e_lfarlc == 0x1C.
    out = bytearray()
    out += struct.pack("<14H", *out_header[:14])
    out += reloc_bytes
    out += b"\x00" * pad
    out += decompressed
    return bytes(out), relocations, (real_ip, real_cs, real_sp, real_ss)


def main():
    if len(sys.argv) != 3:
        print("usage: lzexe_unpack.py <packed.exe> <output.exe>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        packed = f.read()

    output, relocations, entry = unpack(packed)

    with open(sys.argv[2], "wb") as f:
        f.write(output)

    print(f"unpacked {len(packed)} -> {len(output)} bytes, "
          f"{len(relocations)} relocations, entry cs:ip = {entry[1]:04x}:{entry[0]:04x}")


if __name__ == "__main__":
    main()
