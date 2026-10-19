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

## Setup

```
python tools/bootstrap.py   # install pinned toolchain, copy+verify assets, unpack DAVE.EXE
python -m pytest -q
```

The toolchain source defaults to `C:/tools/borland-turbo-c++-1.00/files`
(override with `DAVE_TOOLCHAIN_SRC`); assets default to the primary checkout's
`assets/` (override with `DAVE_ASSETS`). Works in fresh git worktrees.

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

## Status (2026-10-19)

See [docs/dashboard.json](docs/dashboard.json) (generated) and
[docs/matching-phase.md](docs/matching-phase.md).

- **All game code matches the original bytes**, strictly verified (every
  fixup resolved, no masking): 90 C functions in `src/game/` (Turbo C++ 1.00
  `-ms -1- -f- -N -G`) and two TASM 2.0 modules in `src/asm/`.
- Runtime: C0S + 59 CS.LIB modules identified ([docs/library-map.md](docs/library-map.md)).
- Data: all far segments and the level array are rebuilt by exact codecs
  ([docs/data-layout.md](docs/data-layout.md)); EGADAVE.DAV round-trips.
- Packing: LZEXE 0.91 applied to the unpacked image reproduces `DAVE.EXE`.
- In progress: Level C, recovering the translation units and linking the
  whole program with TLINK so the layout emerges instead of being placed.
