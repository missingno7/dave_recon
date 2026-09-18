# Current phase: specimen bootstrap and ownership scaffold

Motto: **first reconstruct what exists, later explain why it exists.**

## Where we are

This project has just started. The concrete state as of this writing:

- Specimen identified and hashed: [docs/specimen-manifest.json](specimen-manifest.json).
- `DAVE.EXE` confirmed LZEXE 0.91-packed; unpacking tool in progress/landed at
  `tools/lzexe_unpack.py` (see [docs/lzexe-unpacking.md](lzexe-unpacking.md)).
- No function census, no compiler identification experiments, and no
  ownership manifest yet exist for the unpacked image — these are the
  immediate next steps.

## Productive frontiers (in rough priority order)

1. **Unpacking correctness.** Prove `tools/lzexe_unpack.py` reproduces a
   byte-correct unpacked image (internally consistent MZ header + relocation
   table; entry point disassembles to sane 8086 code). See
   [docs/blockers.json](blockers.json) for exact open questions.
2. **Ownership bootstrap.** Build `layout/manifest.json` covering the entire
   unpacked image with `RAW_UNKNOWN` regions, so `reconstruct == unpacked
   reference` holds from day one. See `tools/reconstruct.py` (to be written).
3. **Function census.** Conservative function boundaries via linear
   disassembly + call-target discovery, address-based names (`F_XXXX`).
4. **Compiler/toolchain identification.** Compile small C probes with
   candidate Borland/Turbo C versions, memory models, and flags; compare
   emitted OMF against original code regions. Track candidates and results in
   `docs/blockers.json`.
5. **Library identification.** Recognize unchanged compiler runtime library
   contributions (startup code, printf-family, long division helpers, etc.)
   before attempting to hand-decompile them.
6. **EGADAVE.DAV format recovery.** Decode the resource/offset table observed
   at the start of the file, identify chunk types (tiles, sprites, fonts,
   levels), and build encoders that reproduce the original bytes exactly.
7. **First matching-C/ASM promotions.** Small, isolated, high-confidence
   functions first (e.g. simple math helpers, trivial loops) to validate the
   whole compile → OMF-parse → bind → compare loop end to end.

## Explicitly forbidden

- Weakening matching (accepting "looks right" disassembly as proof).
- Discarding quirks or normalizing padding/data to look cleaner.
- Inferring linkage/addresses from comparison at build time instead of from
  recovered linker rules.
- Silent version switching between Dangerous Dave releases.
- Treating the packed `DAVE.EXE` and the unpacked image interchangeably in
  reports — always state which one a given match refers to.

## Ledger

See [docs/blockers.json](blockers.json) for the living, machine-readable
frontier ledger (schema: `dave-mechanical-frontiers-v1`, modeled directly on
`empires_reconstruction`'s `empires-mechanical-frontiers-v1`).
