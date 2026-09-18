# Progress

## 2026-09-18 — Project bootstrap

- Specimen identified and hashed (`docs/specimen-manifest.json`):
  - `DAVE.EXE`: 76,586 bytes, MD5 `10ac35dd6bc6314cd5caf08a4ffb4275`.
  - `EGADAVE.DAV`: 86,332 bytes, MD5 `15e4cfe305600a8acd39d4bc7fe9c591`.
- Confirmed `DAVE.EXE` is LZEXE 0.91-packed (signature `LZ91` at file offset
  0x1c; minimal 32-byte outer MZ header; stub entry point `1298:000E`).
- Ported generic, game-agnostic OMF and MZ header tooling from
  `empires_reconstruction` (`tools/omf.py`, `tools/mz.py`) as the shared
  foundation for later binding/matching work.
- Repository skeleton created (`asm/`, `docs/`, `layout/`, `recipes/`,
  `src/`, `tests/`, `tools/`, `toolchain/`, `assets/`, `raw/`, `build/`,
  `data/`, `formats/`) mirroring `empires_reconstruction`'s directory
  philosophy.
- `docs/vision.md`, `docs/matching-phase.md`, `docs/blockers.json`,
  `docs/build-reconstruction.md` written, adapted from the sibling project's
  templates and its 2026-09-18 "layout must emerge" architectural
  clarification.
- LZEXE 0.91 unpacking tool development started (`tools/lzexe_unpack.py`,
  `docs/lzexe-unpacking.md`) — status tracked in `docs/blockers.json`.

### Byte accounting

Not yet applicable — no ownership manifest (`layout/manifest.json`) exists
yet; this is gated on finalizing the unpacked executable image (see
`docs/blockers.json`, "Executable ownership manifest bootstrap").

### Next milestones

1. Finalize and self-verify LZEXE unpacking.
2. Bootstrap `layout/manifest.json` with 100% byte ownership (mostly
   `RAW_UNKNOWN`) over the unpacked image; verify exact rebuild.
3. Initial function census over the unpacked image.
4. First compiler-identification experiments.
5. First matching-C/ASM promotions.
6. EGADAVE.DAV format decoding.

## 2026-09-18 (cont.) — Unpacking landed, ownership bootstrap milestone reached

- `tools/lzexe_unpack.py` (from-scratch LZEXE 0.91 decompressor) produces
  `build/DAVE_unpacked.exe`: 172,848 bytes, MD5 `86feba8cc84fc1f0d829fd731f6dbe20`,
  SHA1 `9e572f0320ca759bea8f24a0ebcfcb1b68474e13`. **Independently
  cross-checked**: this SHA1 matches a third-party-published
  UNLZEXE-decompressed DAVE.EXE (Internet Archive item "Dangerous Dave (LZW
  decompressed)"), not just internal self-consistency. See
  `docs/lzexe-unpacking.md`.
- **Milestone 1 reached**: `layout/manifest.json` owns all 172,848 bytes of
  the unpacked image across 4 regions (`MZ_HEADER` 28B, `RELOCATION_TABLE`
  108B, `HEADER_PADDING` 376B all-zero, `RAW_LOAD_MODULE` 172,336B raw
  fallback). `tools/reconstruct.py` validates contiguity/no-overlap/no-gap
  and rebuilds the image to exact MD5 match. Verified by
  `tests/test_ownership_bootstrap.py` (5/5 passing).
- String extraction from the unpacked image found `(C) 1990 SOFTDISK, INC.`,
  `BY JOHN ROMERO`, and — most importantly — `Turbo C++ - Copyright 1990
  Borland Intl.`, a linker-embedded runtime string giving direct evidence
  the toolchain is **Turbo C++ 1.0 or 1.01**, not Turbo C 2.0 (used by
  `empires_reconstruction`) or Borland C++ 3.0. Recorded in
  `layout/toolchain.json` (currently unpinned — no local Borland/Turbo C
  installation exists on this machine; project owner decided (2026-09-18) to
  test Turbo C++ 1.0/1.01 first and to supply toolchain binaries locally
  rather than have them downloaded automatically).
- `tools/setup_toolchain.py` written (mirrors `empires_reconstruction`),
  ready to pin and install a supplied Turbo C++ installation once available.

### Byte accounting (as of this update)

| Kind | Bytes | % of unpacked image |
|---|---|---|
| MZ_HEADER | 28 | 0.02% |
| RELOCATION_TABLE | 108 | 0.06% |
| PADDING | 376 | 0.22% |
| RAW_UNKNOWN | 172,336 | 99.70% |
| **Total** | **172,848** | **100%** |

Matching C: 0 bytes. Matching ASM: 0 bytes. Known library: 0 bytes.
Function census: not started.

### Next milestones

1. Obtain a local Turbo C++ 1.0/1.01 installation (blocked on user supplying
   it — see `docs/blockers.json`).
2. Initial function census over `RAW_LOAD_MODULE`, anchored on the located
   `Turbo C++` runtime startup string.
3. First compiler codegen comparison experiments once toolchain is available.
4. EGADAVE.DAV: confirm the 16x16x4bpp EGA planar tile hypothesis by
   decoding and rendering an actual chunk.

## 2026-09-18 (cont. 2) — Toolchain acquired and identity confirmed: Turbo C++ 1.00

- Obtained Borland Turbo C++ 1.0 (May 1990) from Internet Archive's Vintage
  Software Collection (`archive.org/details/borland-turbo-c-plus-plus`, 8
  raw 360K FAT12 floppy images). No `mtools` was available, so a small
  from-scratch FAT12 reader was written to extract files directly from the
  raw disk images; bundled `.ZIP`s were then unzipped normally.
- Installed into `toolchain/` (git-ignored): `TCC.EXE`, `TLINK.EXE`,
  `TLIB.EXE`, per-memory-model startup objects/libraries (compact, small,
  medium, large, huge), and the `INCLUDE/` headers. All pinned by SHA-256 in
  `layout/toolchain.json`. `TASM.EXE` was **not** in this disk set (only
  `TASM2MSG.EXE`) — tracked as a new blocker for future MATCHING_ASM work.
- DOSBox-X (`C:/DOSBox-X/dosbox-x.exe`, already present locally) wired up as
  the compile driver via the new `tools/compile_probe.py`.
- **Compiler identity confirmed directly, not just inferred**: compiling a
  trivial probe (`tests/fixtures/probe1.c`) produced an OMF object whose own
  THEADR/COMENT record reads `TC86 Borland Turbo C++ 1.00` — the compiler
  self-identifying. This matches the `Turbo C++ - Copyright 1990 Borland
  Intl.` runtime string already found in `build/DAVE_unpacked.exe` exactly.
  Full writeup: `docs/toolchain-identification.md`.
- End-to-end pipeline proven: TCC compile -> `.OBJ` -> `tools/omf.py` parse
  -> segment/public extraction (`_TEXT` 13 bytes, public `_add` at offset 0).
  Regression-tested in `tests/test_toolchain_probe.py` (6/6 tests passing
  project-wide).
- `docs/blockers.json`: closed "Historical compiler identity for DAVE.EXE";
  opened "Obtain TASM for MATCHING_ASM promotion" (not yet needed for
  matching-C work).

### Next milestones

1. Initial function census over `RAW_LOAD_MODULE`, anchored on the located
   `Turbo C++` runtime startup string, to find real isolated functions.
2. First real codegen comparison: compile probes under candidate memory
   models/flags and compare against an isolated original function to pin
   down Dangerous Dave's actual build configuration (compact model is only
   an untested starting guess).
3. First matching-C promotion once a memory-model/flags match is found.
4. EGADAVE.DAV: confirm the 16x16x4bpp EGA planar tile hypothesis by
   decoding and rendering an actual chunk.

## 2026-09-19 — First function census: 193 functions found

- Resolved a `_main` address-derivation bug (a 512-byte double-counted
  segment base): the game's `main()` actually starts at file offset 1081
  (0x439), exactly at the `STARTUP_C0S`/`RAW_LOAD_MODULE` manifest boundary
  — not at the previously miscalculated 0x639. Disassembly there shows the
  expected Turbo C++ prologue (`55 8B EC`) followed by a stack-check idiom.
- `tools/function_census.py` scanned for `push bp; mov bp,sp` prologues and
  walked to each function's `RET`/`RETF`, finding **193 candidate
  functions** spanning file offsets 1081–46179 (~45 KB), zero overlaps, zero
  truncations. No further prologue matches occur in the remaining ~126 KB,
  suggesting the `_TEXT` code segment ends near 46179 and the rest is
  `_DATA`/`_BSS` (tracked as a new open frontier, not yet proven).
- Spot-checked candidates: `F_A460`/`F_A469` (9/11 bytes) look like Turbo
  C++ 1.00's `inport`/`inportb`; `F_850A` (12 bytes) wraps `INT 21h AH=9`
  (DOS print string); `F_04FC`/`F_088E` repeat `imul dx` idioms consistent
  with struct-array indexing (candidates for the game's own sprite/tile
  code). None compiled/bound/compared yet — disassembly-pattern guesses
  only, tracked in `docs/blockers.json`.
- Full writeup: `docs/function-census.md`; machine-readable data:
  `docs/function-census.json`. All 7 tests still passing;
  `layout/manifest.json` untouched.

### Next milestones

1. Confirm the `_TEXT`/`_DATA` boundary near file offset 46179.
2. Compile and byte-compare `inport`/`inportb` candidates (`F_A460`,
   `F_A469`) — first real matching-C proof inside game code (not just the
   linked-in runtime library).
3. EGADAVE.DAV: confirm the 16x16x4bpp EGA planar tile hypothesis.

## 2026-09-19 — Coordinate bug fixed; EGADAVE.DAV solved; library scanning + first MATCHING_C; call-graph census

Bootstrap is over — the project moved into productive matching-C
reconstruction this session. Byte accounting for `build/DAVE_unpacked.exe`
(172,848 bytes, 62 owned regions, all gap/overlap tests passing, exact
reconstruction confirmed at every step):

| Kind | Bytes | % |
|---|---|---|
| MZ_HEADER | 28 | 0.02% |
| RELOCATION_TABLE | 108 | 0.06% |
| PADDING | 376 | 0.22% |
| KNOWN_LIBRARY | 3,301 | 1.91% |
| MATCHING_C | 38 | 0.02% |
| RAW_UNKNOWN | 168,997 | 97.77% |

**Coordinate bug fixed permanently.** The earlier "`_main` at file offset
0x639" result was wrong by exactly the 0x200-byte MZ header size, added
twice. Re-derived directly from raw bytes (CALL opcode at file offset
0x2FC, disp16 0x013A): `_main` is at file offset **0x439** (load-module
offset 0x239), confirmed by the expected `55 8B EC` prologue there.
`tools/coordinates.py` now centralizes `file_offset <-> load_module_offset`
conversion and `tests/test_coordinates.py` regression-tests the exact
numbers so this class of bug cannot silently reappear.

**Stack-check flag confirmed empirically**: `-N` (checking ON), not `-N-` —
`docs/flag-investigation.md`, `tests/test_flag_investigation.py`.

**`docs/blockers.json` / `docs/matching-phase.md` cleaned up**: removed
stale/duplicate/contradictory entries, restructured with explicit CLOSED /
PRODUCTIVE_FRONTIER / DEFERRED_NOT_BLOCKING / TRUE_BLOCKER categories.

**Library contribution scanner** (`tools/library_scanner.py`): generalized
the STARTUP_C0S "match modulo fixups" technique across CS.LIB's 312 member
modules. Found **42 exact matches** (2,732 bytes, file offsets
0x9613-0xb49b: ATEXIT, CLOSE, FFLUSH, WRITE, READ, MEMCPY, MEMSET, STRCPY,
INPORT, OUTPORT, long-arithmetic helpers, etc.), most laid out back-to-back
exactly as real linked runtime code — strong evidence these are genuine
matches, not coincidence. All promoted to `KNOWN_LIBRARY` in
`layout/manifest.json`. CC/CM/CL/CH.LIB (other memory models) confirmed to
contribute nothing further, consistent with the small-model finding.
Evidence: `docs/library-scan-evidence.{json,md}`.

**First `MATCHING_C` promotion inside actual game code**: `F_6D64` (file
offset [0x6d64,0x6d8a), 38 bytes) — a compiled `switch(param)` dispatch
head (4-case jump table via near-to-far pointer setup). `src/F_6D64.c`
reproduces the declared extent byte-for-byte with zero unexplained
differences (only fixup-covered bytes differ). Honestly scoped: the source
file's case-body *content* is explicitly documented as placeholder (only
sized to make the dispatch head's non-fixup branch displacement match) —
only the 38-byte dispatch head is claimed as matching, not the case bodies
or jump table that follow (file offset ~0x6d8a-0x6dba), which remain
`RAW_UNKNOWN` and are flagged as the natural next candidate. New reusable
tool: `tools/match_function.py` (candidate.c -> compile -> OMF -> bind
fixups -> full-extent byte compare). Evidence:
`docs/matching-evidence.{json,md}`.

**Function census rebuilt as a call-graph walk** rooted at the trusted
`_main @ 0x439` anchor (previous census was a naive linear prologue scan,
now kept as a frozen baseline at
`docs/function-census-prologue-scan.{json,md}` for cross-reference).
New `docs/function-census.json`: **172 functions**, with callers,
direct callees, confidence, matching_status, and blockers per function;
8 unresolved indirect control-flow targets and 1 overlap anomaly flagged
honestly rather than hidden. Import/verification of
`yo-yo-yo-jbo/dangerous_dave`'s documented facts (same SHA1 specimen) is
in progress as a follow-up (`docs/external-re-evidence.json`, pending).

**EGADAVE.DAV: fully solved, exact round-trip.** Format: `uint32` resource
count (401) + offset table, then two resource kinds by size —
`FIXED_TILE_16x16` (128 bytes, indices 0-52) and `SPRITE_VAR` (variable,
4-byte width/height header, indices 53-400, padded width rounded to a
multiple of 8, always `declared_height + 1` stored rows). 4 EGA bitplanes
in I,R,G,B order, MSB-first, standard 16-color EGA/CGA palette. Visually
confirmed against rendered PNGs (recognizable tiles and Dave sprite
frames), and independently cross-checked against public ModdingWiki
documentation of the format. `tools/egadave_decode.py` /
`tools/egadave_encode.py` round-trip **the entire file exactly**
(re-encoded MD5 == `15e4cfe305600a8acd39d4bc7fe9c591`, zero raw fallbacks).
Evidence: `docs/egadave-format.{json,md}`,
`tests/test_egadave_roundtrip.py`.

All 28 tests passing throughout every change.

### 2026-09-19 (cont.) — External RE import complete; g_levels contradiction caught

`yo-yo-yo-jbo/dangerous_dave` (an independent RE of the same unpacked
executable, SHA1-confirmed identical) was fetched and its facts
individually verified against our own bytes rather than trusted —
discovered and documented that it mixes three unlabeled address
conventions (literal file offsets, IDA `sub_` addresses, raw DS-relative
`word_` operands). Of 10 imported facts: **7 verified** instruction-for-
instruction (game-init, level-completion dispatcher, warp-transition,
score/lives-cap logic, two data tables), **2 contradicted**, **1
could_not_check**. Every verified address was already present in our own
call-graph census — a strong two-way cross-check.

One contradiction is substantive: the external project's claimed `g_levels`
base address (file offset `0x26E0A`) is wrong — that offset is actually a
text string in our bytes ("ENTER FILENAME..."-style prompt), and is
arithmetically inconsistent with the *same* external project's own
separately-verified level-6 warp-bug address. Recorded as a new open
frontier (`docs/blockers.json`: "Re-derive g_levels' true base address")
rather than silently accepted. Evidence:
`docs/external-re-evidence.{json,md}`.

### Next milestones

1. Land more `MATCHING_C` promotions — prioritize the 4 functions with
   now-known semantics from the external-RE import (game-init,
   level-completion, warp-transition, score/lives-cap) and the switch case
   bodies following `F_6D64`.
2. Independently re-derive `g_levels`' true base address (both this
   project's and the external project's guesses are now known-wrong).
3. Resolve the census's 8 unresolved indirect control-flow targets
   (mostly switch jump tables) and its 1 overlap anomaly.
4. Continue the library scan against any newly-classified RAW_UNKNOWN
   regions as more of the code segment is mapped.
5. Confirm the `_TEXT`/`_DATA` boundary using the improved census.
