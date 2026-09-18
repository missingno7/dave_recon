# Toolchain identification: Turbo C++ 1.00

## Direct evidence

Two independent pieces of evidence point at Borland **Turbo C++ 1.00** (May
1990):

1. `build/DAVE_unpacked.exe` embeds the literal runtime startup string
   `Turbo C++ - Copyright 1990 Borland Intl.` (see `docs/specimen-manifest.json`).
2. When compiling a trivial C probe (`tests/fixtures/probe1.c`) with the
   Turbo C++ 1.0 `TCC.EXE` obtained from archive.org (see
   `layout/toolchain.json`), the resulting `.OBJ` file's OMF THEADR comment
   record contains the compiler's own self-identification string:
   **`TC86 Borland Turbo C++ 1.00`**. This is the compiler telling us its own
   exact identity, not an inference — the strongest possible form of
   evidence.

Both strings agree exactly: Turbo C++ 1.00, not 1.01 (Feb 1991) and not
Borland C++ 3.0 (1991).

## Toolchain acquisition

Obtained from Internet Archive's Vintage Software Collection:
<https://archive.org/details/borland-turbo-c-plus-plus> — 8 raw 360K FAT12
floppy disk images, internal file timestamps `1990-05-04`, consistent with
the 1.0 release. Free/legally distributed preservation copy; no local
installation existed on this machine beforehand.

Extraction method: the disk images could not be mounted with `mtools` (not
installed), so a small from-scratch FAT12 reader was written to pull files
directly out of the raw `.img` sector data, then the bundled `.ZIP` archives
(`TCC.ZIP`, `BIN1.ZIP`, `BIN2.ZIP`, per-model library ZIPs, `INCLUDE.ZIP`)
were extracted normally. `TASM.EXE` (Turbo Assembler) was **not** present in
this disk set — only `TASM2MSG.EXE`, a message-file conversion utility.
Assembler-side matching work is blocked on separately obtaining TASM until
then.

DOSBox-X (`C:/DOSBox-X/dosbox-x.exe`, already present on this machine) drives
the actual compiler invocation; see `tools/compile_probe.py` for the minimal
reusable harness and `layout/toolchain.json` for pinned SHA-256 hashes of
every toolchain file now installed locally under `toolchain/` (git-ignored).

## Not yet determined

- Exact memory model used for Dangerous Dave's own code (compact was used as
  the first probe flag, matching `empires_reconstruction`'s Turbo C 2.0
  convention, but this is unverified for Dangerous Dave).
- Optimization/flag combination beyond the starting guess
  (`-1- -f- -N-`, i.e. no 286 instructions, no floating point, no nested
  function checks off).
- Whether any hand-written ASM exists that needs TASM to reproduce.
