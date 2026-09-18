# dave_recon

A lossless reconstruction of the original DOS **Dangerous Dave** into
human-readable source, retaining the ability to reproduce the original
machine representation exactly. Not a source port; not a rewrite.

Modeled on the sibling project `empires_reconstruction`'s methodology. See
[docs/vision.md](docs/vision.md) for the full philosophy,
[docs/matching-phase.md](docs/matching-phase.md) for current priorities, and
[docs/blockers.json](docs/blockers.json) for the live frontier ledger.

## Specimen

- `assets/DAVE.EXE` — main executable, LZEXE 0.91-packed. See
  [docs/specimen-manifest.json](docs/specimen-manifest.json).
- `assets/EGADAVE.DAV` — external EGA resource data (format under
  investigation).

Original game files live in `assets/` and are not committed to git (see
`.gitignore`) — they are the read-only verification fixtures a fresh
checkout must supply locally.

## Layout

```text
asm/        preserved/recovered hand-written assembly source, one file per owned region
docs/       vision, phase direction, progress log, blocker ledger, format writeups
layout/     FIXED-PLACEMENT ownership scaffold (layout/manifest.json) and archive manifests
recipes/    DERIVED/emergent layout path — component order + encoding rules, no offsets
src/        preserved/recovered C source, one file per owned region
tests/      unittest suite validating byte-exact reconstruction
tools/      all build/analysis logic (OMF parsing, MZ header codec, reconstruction, unpacking)
toolchain/  git-ignored local copy of pinned historical compiler/assembler/linker
assets/     git-ignored original game files (verification fixtures only)
raw/        git-ignored per-region raw byte extracts for still-unowned regions
build/      git-ignored generated output
```

## Status

- Specimen identified: 1990 Softdisk *Dangerous Dave* by John Romero.
- `assets/DAVE.EXE` is LZEXE 0.91-packed; `tools/lzexe_unpack.py` unpacks it
  to `build/DAVE_unpacked.exe`, independently cross-checked byte-for-byte
  against a third-party-published decompressed copy.
- **Milestone 1 reached**: 100% of the unpacked image's bytes are owned in
  `layout/manifest.json` with no gaps/overlaps, and `tools/reconstruct.py`
  rebuilds it to an exact MD5 match (currently almost entirely
  `RAW_UNKNOWN` — the real classification work starts next).
- **Toolchain confirmed and installed**: Borland Turbo C++ 1.00 (May 1990),
  obtained from archive.org and pinned in `layout/toolchain.json`. Compiler
  identity is directly confirmed (not inferred) — a compiled probe's OMF
  record contains the compiler's own self-identification string `TC86
  Borland Turbo C++ 1.00`, matching the runtime string embedded in
  `build/DAVE_unpacked.exe`. See `docs/toolchain-identification.md`. Full
  compile -> OMF-parse pipeline proven via `tools/compile_probe.py`.

See [docs/progress.md](docs/progress.md) for the full log and
[docs/blockers.json](docs/blockers.json) for open frontiers.
