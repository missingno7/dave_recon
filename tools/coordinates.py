"""Explicit coordinate systems for the unpacked DAVE.EXE image.

This exists because a naive "just add 0x200" mistake previously produced a
wrong _main address (file offset 0x639 instead of 0x439 -- the MZ header
size was added twice: once correctly, once by accident when a load-module-
relative value was mistaken for a file-relative one and converted again).
See docs/function-census.md and docs/blockers.json for the incident.

There are three coordinate systems in play for this executable:

  file_offset          -- byte offset into build/DAVE_unpacked.exe as a whole,
                           starting at the MZ header (offset 0 = 'M' of "MZ").
  load_module_offset    -- byte offset into the DOS *load module*, i.e. the
                           part of the file the CPU actually executes/reads
                           as memory once loaded. Offset 0 here is CS:IP's
                           segment base (0000:0000) at the game's entry point.
  segment_offset(seg)   -- an offset relative to a specific segment's own
                           base (only meaningful once segment bases are
                           known from a real link; not used yet in this
                           project, but reserved here so callers don't
                           invent their own ad hoc name for it).

For this specimen:

    file_offset = load_module_offset + MZ_HEADER_SIZE   (MZ_HEADER_SIZE = 0x200)

This module provides typed wrappers (not just ints) so mixing the two
systems is a type error, not a silent arithmetic bug, plus plain functions
for callers that only need the conversion.
"""
from __future__ import annotations

import dataclasses

# e_cparhdr (32 paragraphs) * 16, from build/DAVE_unpacked.exe's MZ header.
# See layout/manifest.json's MZ_HEADER + RELOCATION_TABLE + HEADER_PADDING
# regions, which together span exactly this many bytes: [0, 0x200).
MZ_HEADER_SIZE = 0x200


@dataclasses.dataclass(frozen=True, order=True)
class FileOffset:
    """A byte offset into build/DAVE_unpacked.exe (or assets/DAVE.EXE's
    unpacked form generally), counted from the very start of the file."""
    value: int

    def to_load_module(self) -> "LoadModuleOffset":
        if self.value < MZ_HEADER_SIZE:
            raise ValueError(
                f"file offset {self.value:#x} is inside the MZ header "
                f"(< {MZ_HEADER_SIZE:#x}); it has no load-module offset"
            )
        return LoadModuleOffset(self.value - MZ_HEADER_SIZE)

    def __repr__(self):
        return f"FileOffset({self.value:#x})"


@dataclasses.dataclass(frozen=True, order=True)
class LoadModuleOffset:
    """A byte offset into the load module, i.e. relative to CS:IP=0000:0000
    at the game's entry point. This is the coordinate system fixups/relocations
    and disassembly addresses naturally live in."""
    value: int

    def to_file(self) -> FileOffset:
        return FileOffset(self.value + MZ_HEADER_SIZE)

    def __repr__(self):
        return f"LoadModuleOffset({self.value:#x})"


def file_offset_to_load_module(offset: int) -> int:
    """Plain-int convenience wrapper. Raises if offset is inside the header."""
    return FileOffset(offset).to_load_module().value


def load_module_to_file_offset(offset: int) -> int:
    """Plain-int convenience wrapper."""
    return LoadModuleOffset(offset).to_file().value


def resolve_self_relative_call(call_opcode_file_offset: int, disp16: int) -> FileOffset:
    """Resolve a near CALL rel16 (opcode E8, 2-byte little-endian signed
    displacement) to the FileOffset of its target.

    call_opcode_file_offset: file offset of the 0xE8 opcode byte itself.
    disp16: the raw 16-bit displacement value (unsigned; wraps as needed).

    The target is IP-after-the-instruction (opcode + 2 displacement bytes =
    3 bytes total) plus the signed displacement, all within the same
    coordinate system (load-module-relative, since real-mode near calls are
    IP-relative, not file-relative) -- so this function converts to
    load-module offsets internally to do the arithmetic correctly, then
    converts back.
    """
    call_load_offset = FileOffset(call_opcode_file_offset).to_load_module().value
    ip_after = call_load_offset + 3
    # disp16 is a signed 16-bit value; normalize.
    signed_disp = disp16 - 0x10000 if disp16 >= 0x8000 else disp16
    target_load_offset = (ip_after + signed_disp) & 0xFFFF
    return LoadModuleOffset(target_load_offset).to_file()
