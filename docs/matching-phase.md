# Current phase: productive matching-C reconstruction

Motto: **first reconstruct what exists, later explain why it exists.**

Bootstrap is over. The project is no longer blocked on toolchain acquisition,
specimen identification, or ownership scaffolding — see `docs/blockers.json`
for the authoritative, machine-readable ledger. This file gives the human
summary; `docs/blockers.json` is the source of truth if the two ever
disagree.

## CLOSED (settled, do not re-litigate without new evidence)

- LZEXE 0.91 unpacking of `DAVE.EXE` (independently cross-checked hash).
- Historical compiler identity: **Borland Turbo C++ 1.00**.
- Memory model: **small (`-ms`)**.
- Stack overflow checking flag: **`-N` (on)**.
- Executable ownership manifest bootstrap (100% byte ownership, exact
  rebuild).
- `STARTUP_C0S` library-region identification, which also fixed a
  file-offset/load-module-offset coordinate bug (`_main` is at file offset
  `0x439`, not `0x639` — see `tools/coordinates.py` and
  `tests/test_coordinates.py`).

## PRODUCTIVE FRONTIERS (work here)

1. **Function census rooted at `_main @ 0x439`.** Current census
   (`tools/function_census.py`) is a naive prologue scan; it needs to become
   a conservative call-graph walk (direct CALL targets, RET boundaries,
   known prologue/library signatures, cross-references) per
   `docs/blockers.json`.
2. **Import and verify `yo-yo-yo-jbo/dangerous_dave` RE facts.** That
   project analyzes the same unpacked executable (identical SHA1). Its
   documented addresses/facts are hints to mechanically verify against our
   bytes, never accepted as truth on their own.
3. **Scan Turbo C++ 1.00 libraries for more exact library contributions.**
   The technique that identified `STARTUP_C0S` (byte-match modulo fixups)
   generalizes to other runtime helpers. Likely the highest-leverage
   mechanical step available — removes `RAW_UNKNOWN` with zero semantic
   guessing.
4. **First matching-C promotions inside actual game code.** Candidates
   already flagged in `docs/function-census.json` (`F_A460`, `F_A469`,
   `F_850A`, `F_04FC`, `F_088E`). Build a reusable
   candidate→compile→OMF-parse→bind→compare tool, generalizing
   `tools/recover_startup_binding.py`.
5. **Confirm the `_TEXT`/`_DATA` boundary** near file offset `0xB483`.
6. **EGADAVE.DAV structured round-trip.** Independent of the executable
   track — parse the offset table, decode under the planar-tile hypothesis,
   round-trip to byte-identical.

## DEFERRED / NOT CURRENTLY BLOCKING

- TASM acquisition (only once a concrete hand-written-ASM extent needs it).
- Exact LZEXE 0.91 recompression (the unpacked image remains the working
  oracle).
- Historical linker/translation-unit reconstruction (fixed-placement
  ownership remains the proof scaffold; reconstruct progressively once
  enough components exist).
- Confirming the exact Dangerous Dave release/episode variant (our specimen
  is fixed and hashed regardless).

## TRUE BLOCKERS

None currently. If something is only "future work," it belongs in
Productive Frontiers or Deferred, not here — a "blocker" name is reserved
for something that concretely stops a specific piece of work in progress.

## Explicitly forbidden

- Weakening matching (accepting "looks right" disassembly as proof).
- Discarding quirks or normalizing padding/data to look cleaner.
- Inferring linkage/addresses from comparison at build time instead of from
  recovered linker rules.
- Silent version switching between Dangerous Dave releases.
- Treating the packed `DAVE.EXE` and the unpacked image interchangeably in
  reports — always state which one a given match refers to.
- Mixing file-offset and load-module-offset coordinates without going
  through `tools/coordinates.py`.

## Ledger

See `docs/blockers.json` (schema `dave-mechanical-frontiers-v2`) for the
living, machine-readable frontier ledger with explicit categories.
