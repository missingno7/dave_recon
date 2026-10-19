"""The game's own RLE codec (asm at file 0x7E00..0x8058), reimplemented exactly.

Shared state lives in DGROUP (DS:0x1394..0x13A8, accessed through SS):
    0x1394/0x1398  seg/off of argument 1      0x1396/0x139A  seg/off of argument 2
    0x139C/0x139E  u32 count                  0x13A0/0x13A2  u32 bytes emitted (encoder)
    0x13A4         run (repeats of the current byte after its first occurrence)
    0x13A6         current byte               0x13A7         pending literal count

DECODER, entry 0x7ED4 (C wrapper 0x7E00: unrle(src far, dst far, u32 count)):
    control byte b >= 0x80: copy the next b-0x7F bytes (1..128)
    control byte b <  0x80: repeat the next byte b+3 times (3..130)
    It stops as soon as `count` bytes have been produced (it may produce up to
    one chunk more; the game's buffers are large enough).

ENCODER, entry 0x7F41 (never called by the game; it is the tool-side
compressor that was linked in alongside the decoder). Ported instruction for
instruction in `encode` below, including its quirks:
    * It examines `count + 1` source bytes (the loop decrements before reading
      the next byte and stops on borrow), so the byte just past the source
      buffer is always encoded too.
    * After a maximal run (130) or a maximal literal (126) is flushed, if the
      next two bytes both equal the current one it advances the source pointer
      once WITHOUT decrementing the count. Each such "skip" makes it encode one
      more byte past the end of the buffer.
    * When the source offset reaches 0xFF00 it flushes, renormalises seg:off and
      resets the literal start to offset 0, which re-emits the current byte: the
      decoded output then contains that source byte twice.
Encoding the decoded tilesets of segments 0x0C42 and 0x11EF with this port
reproduces both compressed streams byte for byte (tests/test_tilesets_roundtrip.py),
which is strong evidence that this is the compressor that produced them.
"""
from __future__ import annotations

NORMALISE_AT = 0xFF00


def decode(src: bytes, count: int):
    """Port of 0x7ED4. Returns (output, input bytes consumed). Output may exceed
    `count` by the tail of the last chunk, exactly as the asm writes it."""
    out = bytearray()
    i = 0
    while len(out) < count:
        b = src[i]
        if b >= 0x80:
            n = b - 0x7F
            out += src[i + 1:i + 1 + n]
            i += 1 + n
        else:
            out += bytes([src[i + 1]]) * (b + 3)
            i += 2
    return bytes(out), i


def decode_chunks(src: bytes, start: int = 0, end: int = None):
    """Yield (input offset, output length) per chunk in src[start:end]."""
    end = len(src) if end is None else end
    i = start
    while i < end:
        b = src[i]
        if b >= 0x80:
            n = b - 0x7F
            yield i, n, src[i + 1:i + 1 + n]
            i += 1 + n
        else:
            n = b + 3
            yield i, n, bytes([src[i + 1]]) * n
            i += 2


class OverRead(Exception):
    """The encoder needed a byte beyond the memory it was given."""


def encode(memory: bytes, count: int, src_offset: int = 0) -> dict:
    """Port of the encoder at 0x7F41.

    memory      the bytes at and after the source pointer (the source buffer
                followed by whatever lay beyond it in the compressing program)
    count       the u32 count argument (the source length)
    src_offset  offset part of the source far pointer; only matters for where
                the 0xFF00 renormalisation happens

    Returns {"stream", "read" (bytes of memory examined), "normalised_at"
    (memory indices where the renormalisation re-emitted a byte)}.
    """
    out = bytearray()
    seg_base = -src_offset          # memory index of offset 0 in the current segment
    si = src_offset
    litstart = src_offset
    run = 0
    lit = 1
    hi = [0]
    normalised = []

    def rd(off):
        i = seg_base + off
        if i >= len(memory):
            raise OverRead(i)
        hi[0] = max(hi[0], i + 1)
        return memory[i]

    def flush_run():                # 0x7E59
        nonlocal litstart, run
        out.append((run - 2) & 0xFF)
        out.append(cur)
        litstart = (litstart + 1 + run) & 0xFFFF
        run = 0

    def flush_lit():                # 0x7E94
        nonlocal litstart, lit
        out.append((lit + 0x7F) & 0xFF)
        for k in range(lit):
            out.append(rd((litstart + k) & 0xFFFF))
        litstart = (litstart + lit) & 0xFFFF
        lit = 0

    def flush_all():                # 0x802D
        nonlocal lit
        if run:
            if run >= 2:
                if lit >= 1:
                    flush_lit()
                flush_run()
                return
            lit += run              # NB: run itself is not cleared here
        if lit:
            flush_lit()

    remaining = count
    cur = rd(si)                                        # 0x7F44
    while True:
        if si >= NORMALISE_AT:                          # 0x7F50
            flush_all()
            normalised.append(seg_base + si)
            seg_base += si & ~0xF
            si &= 0xF
            litstart = 0
            lit += 1
            cur = rd(si)
            continue
        remaining -= 1                                  # 0x7F8B
        if remaining < 0:
            flush_all()
            return {"stream": bytes(out), "read": hi[0], "normalised_at": normalised}
        si += 1                                         # 0x7F9C
        al = rd(si)
        if al == cur:
            run += 1
            if run < 2:
                continue
            if lit > 1:
                lit -= 1
                flush_lit()
            lit = 0
            if run >= 0x81:
                flush_run()
                if al == rd(si + 1) and al == rd(si + 2):
                    si += 1
            continue
        if run:                                         # 0x7FE7
            if run >= 2:
                flush_run()
            else:
                lit += run
                run = 0
        lit += 1                                        # 0x8004
        cur = al
        if lit >= 0x7E:
            flush_lit()
            if al == rd(si + 1) and al == rd(si + 2):
                si += 1
                lit += 1
