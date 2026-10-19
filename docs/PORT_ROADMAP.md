# Port roadmap: from exact reconstruction to a native, understood Dangerous Dave

Companion documents: `FIDELITY.md` (oracle + equivalence contract),
`NATIVIZATION_LEDGER.md` (machine dependencies -> native services),
`UNDERSTANDING_LEDGER.md` (open semantic questions). Status as of
2026-10-20.

## Guiding decisions

1. **Two trees, one direction of trust.** `src/` + `src/asm/` are the frozen
   historical source (tag `historical-baseline-v1`; `tools/build.py` must
   keep reproducing DAVE.EXE). The native game lives in `port/`, is plain C
   (C11, fixed-width types) built with CMake, and never feeds back into
   `src/`. `tests/test_build.py` guards the baseline on every commit.
2. **The original executable is the oracle.** Native behaviour is accepted
   only through differential comparison with `tools/oracle.py` traces
   (FIDELITY.md), at three granularities: whole game per tick, per
   subsystem call within a tick, and per resource/codec.
3. **Verification bridge, not compatibility layer.** To test native code
   against the original before the whole game is native, tests import an
   original DGROUP snapshot into native state and export native state back
   to the oracle's view (`port/tests/bridge/`). The bridge is the ONLY code
   that knows DS offsets, and it is test-only: the native game never uses an
   emulated memory image, segment addresses or the original layout.
4. **One state model.** A single `struct game` (port/game/state.h) owns all
   gameplay state, designed once from the understood globals (no worker
   invents a parallel representation). Hardware/OS state lives in the
   platform layer, presentation state in the presentation layer.
5. **Three layers** (Phase 7 is where they are finalised, but code is
   written into them from the start):
   - `port/game/` pure simulation: `game_tick(struct game*, const struct
     tick_input*)`, deterministic, headless, no I/O.
   - `port/present/` original logical presentation: 320x200 indexed
     framebuffer per original video mode, text, sound *requests* -> logical
     tone timeline, resource readers (built from the existing codecs'
     format knowledge).
   - `port/platform/` SDL3 (window, audio synthesis, input devices, files,
     clock) and a headless backend.

## Phases, milestones and gates

### Phase 0 -- historical baseline: DONE (2026-10-20)
All game code matches (90 C functions in 3 recovered units, 2 TASM modules),
data rebuilt from codecs, TLINK lays everything out, LZEXE reproduces
DAVE.EXE (`tools/build.py`, `tests/test_build.py`). Frozen as
`historical-baseline-v1`.
*Residual (does not block):* the asm modules still reference C globals by
placeholder names, bound at link time by `tools/link_probe.py` (adopt the
names in `src/asm`); data-module provenance unknowable (D-2).

### Phase 1 -- deterministic oracle: IN PROGRESS
- [x] M1.1 `tools/oracle.py`: per-tick DGROUP + framebuffer + sound requests,
      emulated time, pinned clock; contract holds across 3 runs (attract).
- [ ] M1.2 Per-subsystem boundary snapshots: on_exec at each of the 13
      call sites in `main`'s loop (cs 0x283..0x2a7), so every native
      subsystem can be verified in isolation (bridge, decision 3).
- [ ] M1.3 Scenario corpus: all 5 demos; scripted per-level play; high-score
      persistence (DSCORES.DAV after run); config screens.
- [ ] M1.4 CGA/EGA capture (EGA planar memory needs plane-aware dumps).
- [ ] M1.5 `tests/test_oracle.py` (opt-in, slow): repeat-run contract.
**Gate:** every corpus scenario passes the repeat-run contract.

### Phase 2 -- complete semantic recovery
- M2.1 Generated semantic inventory (`docs/semantic-inventory.json`): every
  function, asm proc, global, data object with status (understood /
  partial / behaviour-only / representation-only / unresolved) and evidence,
  drawn from source headers and the ledgers.
- M2.2 Close UNDERSTANDING_LEDGER items, driven by oracle experiments
  (watchpoints on specific fields, boundary snapshots).
- M2.3 Design `struct game` from the inventory (decision 4).
**Gate:** no gameplay-relevant item unresolved; remaining unknowns explicit.

### Phase 3 -- readable native-oriented source
- M3.1 `port/` skeleton: CMake, headless runner, bridge, CI target that
  runs native unit tests without SDL.
- M3.2 Translate subsystems into `port/game/` one at a time, each verified
  against M1.2 boundary snapshots: pure logic first (tiles/collision,
  items, levels/warps, monsters, shots, player, death, demo input), then
  menus/high scores.
**Gate:** the whole tick pipeline is native and per-tick equivalent on the
corpus (state level).

### Phase 4 -- assembly algorithms -> C
Rendering (tiles, masked sprites, save/restore-under, view, text, pictures),
RLE, RNG, sound driver, each re-expressed as an algorithm on native data,
verified against framebuffer snapshots / codec tests / sound-request + tone
timelines.
**Gate:** no 8086 assembly needed; framebuffer-equivalent on the corpus.

### Phase 5 -- remove segmented memory and CPU assumptions
Typed buffers instead of far/huge pointers, explicit 16-bit arithmetic where
observable, native structs instead of parallel arrays, each layout-dependent
quirk (U-M1) reproduced intentionally and documented.
**Gate:** game code has no original addresses; bridge is the only mapping.

### Phase 6 -- replace DOS/BIOS/hardware/runtime services
Input (key table, bioskey queue, joystick, mouse), video modes, sound
scheduling + synthesis, files, RNG (exact Borland `rand` LCG where
observable), time seed. **Gate:** no DOS/BIOS/hardware/runtime dependency.

### Phase 7 -- final architecture (the three layers) + SDL3 backend
Architecture quality tests from the brief (10,000 headless steps without
SDL; render without stepping; present at any rate; audio without a device).

### Phase 8 -- full differential equivalence
Whole-corpus replay at state, framebuffer and sound levels, first-divergence
diagnostics, documented verification contract and coverage.

### Phase 9 -- cleanup and self-sufficiency
Remove migration leftovers; Windows + Linux builds; no historical tool
needed to build or run.

### Phase 10 -- enhancements (out of scope until Phase 9 gate)

## Dependencies and parallelism

- Phase 0 is complete, so nothing native is blocked on historical matching.
- Can run in parallel now: M1.2/M1.3 (oracle), M2.1 (inventory), M1.4
  (CGA/EGA capture), asm placeholder renames (Phase 0 residual).
- M2.3 (state model) gates M3.2; M3.1 skeleton can start once M2.3's
  struct design is agreed. Rendering (Phase 4) needs M1.2's framebuffer
  snapshots per subsystem.

## Current next milestone

M1.2 -- per-subsystem boundary snapshots in the oracle, then M2.1 the
generated semantic inventory. Both are independent, verifiable, and unblock
native subsystem work.
