# Fidelity: reference behaviour, replay, equivalence

The original `DAVE.EXE` (SHA-256 `1ae779823df27f2c...`) is the behavioural
oracle for the native port. It is never the port's runtime. This document
defines how we observe it, what "equivalent" means, and what is and is not
covered.

## 1. The original execution model (what we now know)

All facts below are from recovered source (`src/*.C`, `src/asm/*.asm`) plus
the oracle traces (`tools/oracle.py`).

- **One game tick = one pass of `main`'s loop** (`src/DAVE.C main`): 13
  subsystem calls in fixed order: `attract_mode`, `process_input`,
  `move_dave`, `update_explosions`, `move_monsters`, `move_bullets`,
  `animate_tiles`, `check_collisions`, `pick_up_items`, `level_complete`,
  `check_warp_transition`, `update_jetpack`, `handle_death`. The loop runs
  until `game_over` (DS 0x5792).
- **Pacing is the display's vertical retrace, not a timer.** `WaitVBL`
  (`lowlevel.asm`, F_7831: poll port 3DAh bit 3) is called once per tick
  inside `move_dave`. So the simulation rate is the refresh rate of the
  chosen video mode: **70.086 Hz in VGA mode 13h** (measured: 14.27 ms
  between ticks over 600 demo ticks). Some ticks take several retraces:
  horizontal scrolling redraws 15 columns with one retrace each
  (`scroll_screen`), and death and level-transition sequences have their own
  waits. EGA (mode 0Dh) and CGA (mode 4) run at their own refresh rates
  (not yet measured -> UNDERSTANDING_LEDGER U-T2).
- **Sound is asynchronous.** `StartSound` reprograms PIT channel 0 and hooks
  INT 8. The ISR steps through the current sound's PIT-divisor list at a
  per-sound rate (`TickDivide`/`TimerRate`) and chains the BIOS INT 8 every n
  ticks. The game only *requests* sounds (`PlaySound(n)`, priority-based).
  The tone stream runs on the PIT clock, not on game ticks.
- **The title screen timeout is measured in real time** (the asynchronous
  timer), so the number of retraces before the first demo tick varies by
  one depending on PIT/retrace phase.
- **Randomness**: `srand(time())` at start-up plus the asm lagged-Fibonacci
  generator (`InitRnd`/`Random`). The oracle pins the DOS date and time.

## 2. The oracle harness

`python tools/oracle.py tests/oracle/<scenario>.txt [--repeat N]`

- Pinned emulator: DOSBox-X 2026.08.31 "acceptance" build v3 (SHA-256
  `e5b9a81a...`, `C:/tools/CATALOG.md`): scripted key down/up, memory dumps
  on instruction execution, port I/O logging, all in **emulated** time.
- Pinned conditions: `cycles=fixed 20000`, 386, normal core, svga_s3 (the
  game auto-selects VGA mode 13h), DOS date 01/01/1991 00:00:00, pristine
  copies of DAVE.EXE / EGADAVE.DAV / DSCORES.DAV, DAVE typed at emulated
  3000 ms (starting it from autoexec showed ~1 ms of host-dependent boot
  jitter). The load segment (0x0824) is re-derived on every run.
- Captures, per **game tick** (hit of `main`'s loop head, cs 0x0283):
  - the complete live DGROUP (DS 0x0000-0x9F20), raw and with named fields
    decoded (`ticks.jsonl`);
  - the VGA framebuffer (64000 bytes; PNG every N ticks);
  - the number of retraces since the previous tick.
- Captures, per event: every `PlaySound(n)` call with the tick it occurred
  in (`sounds.jsonl`) and the raw PIT/speaker port stream (`pit.log`).

## 3. Equivalence contract (as implemented in `compare_runs`)

Two runs are equivalent when:

| level | compared | rule |
|---|---|---|
| gameplay state | per-tick DGROUP | byte-exact, excluding DS [0x1384,0x1392) (INT 8 driver phase: TickDivide, TickCount, TimerRate, SoundPtr, SoundPriority, saved copies) |
| timing | retraces between consecutive ticks | exact, except the interval after a title-screen tick (real-time timeout) |
| sound | sequence of (tick, sound id) | exact |
| visuals | per-tick framebuffer | byte-exact |
| persistence | DSCORES.DAV after the run | exact (planned: scenario-level check) |

Not part of the contract, and kept for analysis only: absolute emulated
times (the emulator shows sub-microsecond scheduling jitter between runs),
the raw PIT stream, and DRAM-refresh bit 4 of port 61h.

**Self-consistency of the oracle (2026-10-20):** `tests/oracle/attract.txt`
(30 s: title screen, then the first attract demo, played on level 2 -- `level` = 1, zero-based) is EQUIVALENT across 3 independent
runs over 656 common ticks: identical per-tick state, retraces, 52 sound
requests and framebuffers.

## 4. Comparing the native port (Phase 8 design)

The native game exposes a **state projection**: a function that maps its
native state to the oracle's observable fields (first the named fields in
`tools/oracle.py FIELDS`, growing to every semantically understood DGROUP
variable) plus its logical framebuffer and its sound-request log. The
native headless runner replays the same input (taken per tick from the
oracle's key-state table, `key_down[128]` at DS 0x8A32, captured in every
tick snapshot) and must match the oracle tick for tick. The first diverging
tick and field are reported. A mismatch is fixed in the semantic layer that
owns it, never by special-casing the comparison.

Equivalence is claimed only over the tested corpus. It is not a proof over
all states; the corpus and its coverage are listed with each claim.

## 5. Scenario corpus (planned order)

1. `attract` -- title + built-in demos (done; 30 s). Extend to all 5 demos.
2. Scripted play per level: walk/jump/climb/jetpack/gun, item pickup,
   death, warp zones (incl. the level-6 warp bug), level completion.
3. High-score entry and DSCORES.DAV persistence.
4. Configuration screens (keyboard/joystick/mouse set-up).
5. CGA and EGA presentation (machine=cga / ega) -- separate framebuffer
   capture paths (planar EGA memory needs register-aware capture).
6. Timing-sensitive cases (scroll during movement, multi-retrace ticks).
