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
   - `port/game/` pure simulation: `game_step(struct game*, const struct
     frame_input*, struct frame_output*)` advances ONE retrace ("frame",
     state-model.md D2); multi-retrace sequences are explicit state; the
     output is the ordered draw-command list (D1) and sound requests.
     Deterministic, headless, no I/O.
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
- [x] M1.2 Per-subsystem boundary snapshots: `boundaries <n>` in a scenario
      dumps DGROUP at all 14 pipeline points (13 call sites + end of tick) for
      the first n ticks into `boundaries.bin` (XOR-delta + zlib;
      `oracle.iter_boundaries`). Verified: end-of-tick == next tick start;
      reproducible across runs (`tests/oracle/attract_boundaries.txt`).
- [ ] M1.3 Scenario corpus: all 5 demos; scripted per-level play; high-score
      persistence (DSCORES.DAV after run); config screens.
      *Partial (2026-10-20):* all 5 demos (attract_all_demos), level 1
      played to the door, deaths/game over/high-score entry with
      DSCORES.DAV compared, the out-of-range demo quirk; persistence is in
      the contract. Open: live play beyond level 1, warp zones, level -1
      warp, config screens (FIDELITY.md section 5, ledger U-O1).
      *Second pass (2026-10-20, oracle lane):* scripted routes planned with
      tools/route.py (native pipeline as simulator, original as judge):
      levels_1_to_3, jetpack_fuel_out, warp_zone_level5 (levels 1-4, level 5's
      warp zone in and out, the U-G9 a multi-bit tree grab), warp_zone_death;
      title_popups (F1/F2/F3/F9/Esc/F10 left unchanged), demo_key_exit (demo
      ended by a key, menus in play, F3 restart). Level -1: see FIDELITY.md
      section 5.
- [x] M1.4 CGA/EGA capture: `video ega|cga`; CGA B800 dump is complete;
      EGA per-tick read-map plane + true 4-plane images inside
      `SaveUnderEGA` (`ega_planes`); retrace rates measured (59.92 Hz).
      A 4-plane image at every tick head needs an emulator command (U-O2).
- [x] M1.6 Retrace-granularity observation (state-model.md D2): a capture
      point at `WaitVBL`, per-frame input reconstruction from scenario
      scripts, draw-order capture for the D1 draw-command contract.
      *Partial:* `retraces <n>` captures DGROUP + BIOS key buffer at every
      `WaitVBL` exit with the script's held keys, and a per-retrace contract
      (level1_complete, game_over_highscore). Open: draw-order capture.
      *Done (2026-10-20):* `draws <n>` writes draws.jsonl (every drawing
      routine's entry with its arguments, merged with the WaitVBL exits,
      leaf/wrapper marking and the output.h op per call; FIDELITY.md
      section 6), reproducible on attract_boundaries and level1_complete;
      plus per-tick key table at process_input's read (keys_at_read.jsonl),
      the BIOS key buffer at every tick head and WaitVBL counts per tick.
- [x] M1.5 `tests/test_oracle.py` (opt-in: DAVE_ORACLE_TESTS=1): repeat-run contract.
**Gate:** every corpus scenario passes the repeat-run contract.

### Phase 2 -- complete semantic recovery
- M2.1 Generated semantic inventory (`docs/semantic-inventory.json`): every
  function, asm proc, global, data object with status (understood /
  partial / behaviour-only / representation-only / unresolved) and evidence,
  drawn from source headers and the ledgers. *Done 2026-10-20:*
  `tools/semantic_inventory.py` (`--check`, `tests/test_semantic_inventory.py`)
  writes `docs/semantic-inventory.{json,md}`: 90 C functions, 60 asm
  procedures, 226 data objects, 17 record formats, 19 subsystems, relations
  parsed mechanically and cross-checked against the binary call graph.
- M2.2 Close UNDERSTANDING_LEDGER items, driven by oracle experiments
  (watchpoints on specific fields, boundary snapshots). *In progress:*
  U-G1..U-G8, U-S1, U-S2, U-M1, U-M2 closed (`tools/semantic_experiments.py`
  on `tests/oracle/inv_demos*.txt`); open: U-G9, U-M3, U-R*, U-T*.
- M2.3 Design `struct game` from the inventory (decision 4). *Proposal:*
  `docs/state-model.md`, awaiting approval (questions Q1-Q7 there).
**Gate:** no gameplay-relevant item unresolved; remaining unknowns explicit.

### Phase 3 -- readable native-oriented source
- M3.1 `port/` skeleton: CMake, headless runner, bridge, CI target that
  runs native unit tests without SDL. *Started 2026-10-20:* CMake (C11,
  MinGW gcc), `port/game/anim.c` (first native subsystem), test-only bridge
  `port/tests/bridge/`, differential driver `tools/native_check.py` --
  the whole verification pipeline is proven end to end on `animate_tiles`.
- M3.2 Translate subsystems into `port/game/` one at a time, each verified
  against M1.2 boundary snapshots: pure logic first (tiles/collision,
  items, levels/warps, monsters, shots, player, death, demo input), then
  menus/high scores. *Done for the pipeline (2026-10-20):* all 13 pipeline
  subsystems are native and verified in isolation (NATIVIZATION_LEDGER D).
- M3.3 Compose the native subsystems into a native game tick and run the
  native game FREE against the original. *Done 2026-10-20:*
  `port/game/game.c` `game_tick()` = one pass of main()'s inner loop (the 13
  calls in the original order, one `frame_output` per pass, the inner loop's
  exit on game_over); `port/tests/replay/replay.c` + `tools/native_replay.py`
  import the original state ONCE (tick 1, the title) and then run on inputs
  only (key table at each pass's first poll, the scenario's key events,
  tick-head times, time(NULL)). Every pass of the corpus is equal on the
  game view (native_check's mask), the PlaySound sequence and the WaitVBL
  count: `n3_level1_complete` 943 passes (title, level 1, corridor, level 2),
  `game_over_highscore` 2,235 (four deaths, game over; stops at the
  game-over pass, whose successor is check_high_score's), `inv_demos_all`
  5,387 and `n2_demos` 11,440 (all five demos, high-score/title cycles,
  demo choices by time(NULL)), `n1_ega_demo2` / `n1_cga_demo2` 819 each.
  Elapsed retraces (`frames_since_prev`) equal too, except where the
  original's elapsed time is not its WaitVBL count: WaitSound (asynchronous
  sound driver) and the title prompt (FIDELITY.md 3), and one CGA scroll pass
  whose redraws overrun a CGA frame (U-P1). No struct game field was
  missing; nothing is re-read from the original between ticks.
  `tests/test_native.py NativeFreeRunTest` (+ mutants: subsystem order,
  gem value). Outside the pipeline, not yet native: check_high_score,
  init_game_once, the menus/popups and the demo end by a key (game_tick
  stops the pass and returns the request, game.h).
**Gate:** the whole tick pipeline is native and per-tick equivalent on the
corpus (state level). *Met 2026-10-20 for the pipeline* (M3.3: free-running,
state + sound requests + WaitVBL counts, 21,643 passes over six runs incl.
EGA and CGA); open for the code outside it (check_high_score, menus, demo
exit by key, init_game_once) and for the corpus gaps (U-O1: warps, levels
3-10 by keyboard, the ending).

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

M1.3 (scenario corpus: all demos, scripted play, persistence) and M2.1 (the
generated semantic inventory), in parallel; then M2.3 the native state model
and M3.1 the `port/` skeleton with the verification bridge.
