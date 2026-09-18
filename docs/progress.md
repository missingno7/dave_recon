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
