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
- **CS.LIB library scan**: 42 exact library-module matches (2,732 bytes)
  found and promoted to `KNOWN_LIBRARY` via `tools/library_scanner.py`.
- **Function census rooted at `_main @ 0x439`**: rebuilt as a call-graph
  walk, 172 functions found (`docs/function-census.json`).
- **First `MATCHING_C` promotion inside game code**: `F_6D64` (38-byte
  switch dispatch head), via the new reusable `tools/match_function.py`.
- **EGADAVE.DAV**: fully solved, exact byte-for-byte round-trip proven.

## PRODUCTIVE FRONTIERS (work here)

1. **Continue matching-C promotions.** 1 of 172 census functions promoted
   so far. Next candidate: `F_6D64`'s own case bodies/jump table (file
   offset ~`0x6d8a`-`0x6dba`). Beyond that, rank the remaining census
   functions by ease-of-matching (leaf, no indirect control flow, few
   external calls, simple arithmetic, table indexing) and work through them
   with `tools/match_function.py`.
2. **Import and verify `yo-yo-yo-jbo/dangerous_dave` RE facts.** In
   progress — that project analyzes the same unpacked executable (identical
   SHA1). Its documented addresses/facts are hints to mechanically verify
   against our bytes, never accepted as truth on their own.
3. **Confirm the `_TEXT`/`_DATA` boundary**, now informed by the call-graph
   census and library scan results rather than the old naive-scan guess.
4. **Re-run the library scanner** against newly-classified regions
   periodically as more of the code segment is mapped.
5. **Resolve the census's 8 unresolved indirect control-flow targets**
   (likely switch jump tables) and its 1 overlap anomaly.

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
