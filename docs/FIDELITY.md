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
  chosen video mode. Measured (mean over the play/demo ticks of a run, total
  emulated time / total retraces):

  | adapter (DOSBox-X machine) | mode | retrace period | rate | evidence |
  |---|---|---|---|---|
  | VGA (svga_s3) | 13h | 14.2689 ms | 70.08 Hz | attract.txt, 657 retraces |
  | EGA (ega) | 0Dh | 16.6897 ms | 59.92 Hz | ega_attract.txt, 507 retraces |
  | CGA (cga) | 4 | 16.6880 ms | 59.92 Hz | cga_attract.txt, 507 retraces |

  These are DOSBox-X's models of the real timings (VGA 25.175 MHz / 800 /
  449 = 70.086 Hz; EGA and CGA 200-line modes 14.318 MHz / 912 / 262 =
  59.92 Hz), so the EGA and CGA games run 14.5% slower than the VGA game
  (UNDERSTANDING_LEDGER U-T2). Some ticks take several retraces: horizontal
  scrolling redraws 15 columns with one retrace each (`scroll_screen`: a
  scroll tick is 16 retraces), and death and level-transition sequences have
  their own waits. One tick takes NO retrace: the tick in which Dave's
  killed bit (0x40) is processed (`move_dave`'s final branch erases him and
  spawns the explosion without `WaitVBL`), so two tick heads fall into one
  retrace (`frames_since_prev` 0; game_over_highscore.txt tick 921).
- **Sound is asynchronous.** `StartSound` reprograms PIT channel 0 and hooks
  INT 8. The ISR steps through the current sound's PIT-divisor list at a
  per-sound rate (`TickDivide`/`TimerRate`) and chains the BIOS INT 8 every n
  ticks. The game only *requests* sounds (`PlaySound(n)`, priority-based).
  The tone stream runs on the PIT clock, not on game ticks.
- **The DOS time of day runs slow while the game plays sounds.** Every
  accepted `PlaySound` reprograms PIT channel 0 (restarting its count) and
  resets `TickCount` to `TickDivide`, so the partial BIOS tick in progress is
  lost; `StopSound`/`PauseSound` do the same. Measured from the srand seeds
  (= time() & 0xFFFF) of attract_all_demos.txt: the DOS clock advanced 39 to
  62 s between demo choices that were 40.6 to 66.1 s of emulated time apart,
  overall 0.93-0.94 of emulated time over 400-600 s of attract mode. Since
  the attract demo is chosen by `srand(time(NULL))`, this matters for which
  demo plays (state-model.md D7: time is an input).
- **The title screen timeout counts 1,200 retraces** (`attract_mode` state 3:
  200 x 6 `WaitVBL`), not real time. The +-1 retrace that earlier runs showed
  between the title tick and the first demo tick was not in the game: it was
  the emulator (next item); with the pinned `frameskip=1` every run of every
  scenario shows the same count (1201 retraces in VGA, 1201/1202 in EGA/CGA
  depending on the scenario, equal across repeats). The uninitialised title
  animation counter `j` (U-R5) cannot cause it: it only selects the tile drawn,
  not the number of `WaitVBL` calls, and the title framebuffers are equal
  across repeats.
- **Emulator finding: DOSBox-X's retrace timeline is not deterministic with
  `frameskip=0`.** `VGA_VerticalTimer` (hardware/vga_draw.cpp) corrects the
  frame period by up to 0.1 ms per frame (`vsync_adj`) towards a timeline
  computed from a frame counter that is maintained in the rendering path
  (`vga_mode_frames_since_time_base`, line-drawing events, `RENDER_StartUpdate`
  / `GFX_StartUpdate` on the host). With frameskip 0, identical scenarios
  gave retrace timelines offset by 0.2-1.3 ms and by whole frames (15.3 ms,
  30.5 ms, once 81 ms through a title poll) relative to the emulated clock,
  decided around video mode sets; 4 of 8 runs of one scenario differed. The
  game logic is deterministic in ticks, but scripted keys are given in
  emulated milliseconds, so the same script reached different ticks (one run
  pair diverged at tick 4, another at tick 290). With `[render] frameskip=1`
  (now pinned in `oracle.py`), 24 of 24 runs of the same scenario stayed
  within one 2.7 ms window ([0, 2.7] ms after the earliest), with no frame
  shifts. `frameskip=9` made it worse (6 of 8 runs shifted by a frame).
  Remaining jitter: a per-run constant of up to 2.7 ms after each video mode
  set; the input-snapping rule below absorbs it.
- **Input sampling.** `process_input` reads the key table right after the
  tick head; `fire`/`jetpack` act on the button's release (or every 30 held
  ticks: `g_fire_repeat` / `g_jetpack_repeat`). `g_input_dir` keeps the last
  pressed direction until `move_dave` consumes it on an acting tick, so a
  direction tapped for one tick still acts. Walking moves 2 px every 3rd
  tick, jumping and climbing act every 2nd tick, falling and the jetpack
  every tick (`g_death_pause`); reversing direction while walking adds an
  extra 2 px step (`g_prev_dir`). Blocking waits poll on retraces: the title
  every 6, `wait_for_input` every 20, `wait_key_cursor` every 5.
- **Randomness**: `srand(time(NULL))` (16-bit seed: the low word of
  time(), with Borland's default EST offset) chooses the attract demo;
  `load_level` reseeds with `srand(100)`, so all in-level randomness is the
  same on every load. The oracle pins the DOS date and time.
- **Attract demo sequencing** (attract_all_demos.txt header): demo =
  rand() * 5 / 32767 after `srand(time)`; demos end at their 0x30 byte
  (game_state 2), the next tick shows the high scores (1000 retraces) and the
  title (1200) before the next choice. From DOS 00:00:00 the choices are
  1, 3, 0, 4 and then 1, 4 forever: demo 2 never plays. Seeds 3501 and 7002
  give index 5 (out of the table): a garbage "demo" that ends frozen in
  `wait_for_input` (attract_out_of_range_demo.txt).

## 2. The oracle harness

`python tools/oracle.py tests/oracle/<scenario>.txt [--repeat N] [--snap]`
`python tools/oracle.py --report build/oracle/<scenario>/run1`

- Pinned emulator: DOSBox-X 2026.08.31 "acceptance" build v3 (SHA-256
  `e5b9a81a...`, `C:/tools/CATALOG.md`): scripted key down/up, memory dumps
  on instruction execution, port I/O logging, all in **emulated** time.
- Pinned conditions: `cycles=fixed 20000`, 386, normal core,
  `[render] frameskip=1` (section 1), DOS date 01/01/1991, time 00:00:00
  unless the scenario says `dos_time`, pristine copies of DAVE.EXE and
  EGADAVE.DAV (there is no DSCORES.DAV in `assets/`: the game writes its
  default table at start-up), DAVE typed at emulated 3000 ms. The load
  segment (0x0824) is re-derived on every run.
- Scenario options: `duration`, `png_every`, `boundaries <n>` (M1.2),
  `video vga|ega|cga` (machine svga_s3 / ega / cga; the game's `VideoID`
  then picks mode 13h / 0Dh / 4), `dos_time HH:MM:SS`, `ega_planes <n>`,
  `retraces <n>` (M1.6), and `<ms> key|keydown|keyup <mapper name>`.
- Captures, per **game tick** (hit of `main`'s loop head, cs 0x0283):
  - the complete live DGROUP (DS 0x0000-0x9F20), raw (`ticks.bin`) and with
    named fields decoded (`ticks.jsonl`, incl. `keys_down`, the scan codes
    set in `key_down[128]`);
  - the video memory: VGA A000:0000 64000 bytes; CGA B800:0000 16 KB; EGA
    A000:0000 8000 bytes of the bit plane the graphics controller's read map
    selects at that instant (a CPU read of planar memory sees one plane; in
    practice plane 0, which every EGA blitter leaves selected);
  - the number of retraces since the previous tick.
- **EGA 4-plane images** (`ega_planes <n>`): the acceptance build can only
  dump guest memory through the CPU's view, so the true planes are read
  where the game itself selects each plane for reading: `SaveUnderEGA`
  (read-only) at cs 0x8545, right after its read-map `out`; the first
  line's four dumps (AH = 3, 2, 1, 0 with the same BL) form one consistent
  image, the screen just before `draw_dave` draws Dave
  (`ega_planes.jsonl`, `ega*_tick*.png`). The dump's own reads reload the
  latches, which is harmless there (the next game instruction reads memory
  again). A full 4-plane image at every tick head would need an emulator
  command that reads `vga.mem.linear` directly (not in build v3).
- **Per-retrace capture** (`retraces <n>`, M1.6, state-model.md D2): at
  every `WaitVBL` exit (cs 0x7640, right after port 3DAh bit 3 rose) the
  DGROUP and the BIOS keyboard buffer (0040:001A..003D); `retraces.bin`
  (XOR-delta + zlib, `oracle.iter_retraces`) and `retraces.jsonl` (per
  retrace: the tick it belongs to, gameplay hash, `keys_down`, pending BIOS
  keys, and the keys the scenario script holds at that time).
- Per event: every `PlaySound(n)` with its tick (`sounds.jsonl`), every
  `srand(seed)` with its tick (`seeds.jsonl`), the raw PIT/speaker port
  stream (`pit.log`).
- After the run: name, size and SHA-1 of every file in the game directory
  (`summary.json` `files`), i.e. DSCORES.DAV and anything the game wrote.
- **Input snapping (`--snap`).** Key events are given in emulated ms but the
  game samples them at tick heads / retraces, and the retrace phase has the
  2.7 ms jitter above. `--snap` runs the scenario once and moves every event
  to the middle of its sampling window in that run: with a `retraces`
  capture, half-way between the two `WaitVBL` exits around it; without, the
  middle of a one-retrace tick, or 10.5 retraces before the head of a long
  tick (`wait_for_input`'s poll period). The per-tick input is unchanged, so
  the run's tick times stay valid. Rules for authors: no `key` taps where the
  state is compared (a 50 ms tap is 3.504 VGA retraces long, so its release
  lands on a retrace edge); press and release keys of blocking prompts
  (title, high-score initials, Enter) well inside their poll windows.

## 3. Equivalence contract (as implemented in `compare_runs`)

Two runs are equivalent when:

| level | compared | rule |
|---|---|---|
| gameplay state | per-tick DGROUP | byte-exact, excluding DS [0x1384,0x1392) (INT 8 driver phase: TickDivide, TickCount, TimerRate, SoundPtr, SoundPriority, saved copies) |
| per-retrace state | DGROUP + key table at every `WaitVBL` exit (when captured) | byte-exact (same exclusion), per tick, for every tick whose interval is under the timing rule |
| timing | retraces between consecutive ticks | exact, except the interval after a title tick (game_state 3) and the interval ending at a title tick (game over: high-score table and initials) |
| sound | sequence of (tick, sound id) | exact |
| visuals | per-tick framebuffer; EGA 4-plane captures | byte-exact |
| persistence | every file of the game directory after the run | name, size, SHA-1 equal |

The timing exemption covers intervals that contain `WaitSound` (a busy wait
on the asynchronous PIT-driven sound driver, in `show_high_scores(1)`) or
keyboard prompts paced by the scenario's absolute times (`input_initials`,
title). It was widened on 2026-10-20 to the interval that ENDS at a title
tick: that interval is game over -> `check_high_score` (table with
`WaitSound`, "You got a high score!", initials, Enter), the same kind of
wait as the already-exempt one. The state inside them is still compared.

Not part of the contract, and kept for analysis only: absolute emulated
times (section 1: a constant per-run offset of up to 2.7 ms), the raw PIT
stream, and DRAM-refresh bit 4 of port 61h.

**Self-consistency of the oracle:** every scenario of section 5 is
EQUIVALENT across 2 independent runs (2026-10-20, frameskip=1).

## 4. Comparing the native port (Phase 8 design)

The native game exposes a **state projection**: a function that maps its
native state to the oracle's observable fields (first the named fields in
`tools/oracle.py FIELDS`, growing to every semantically understood DGROUP
variable) plus its logical framebuffer and its sound-request log. The
native headless runner replays the same input (taken per retrace from the
oracle's key-state table, `key_down[128]` at DS 0x8A32, and the BIOS key
buffer, captured at every `WaitVBL` exit) and must match the oracle frame
for frame. The first diverging frame and field are reported. A mismatch is
fixed in the semantic layer that owns it, never by special-casing the
comparison.

Equivalence is claimed only over the tested corpus. It is not a proof over
all states; the corpus and its coverage are listed with each claim.

## 5. Scenario corpus

All are EQUIVALENT under `--repeat 2` (2026-10-20). Tick ranges and the
evidence for each claim are in each file's header.

| scenario | video | covers | ticks / length | per-retrace |
|---|---|---|---|---|
| `attract.txt` | VGA | title (1201 retraces), demo 1 on level 2 (its first 658 ticks) | 659 ticks, 30 s | - |
| `attract_boundaries.txt` | VGA | as attract, per-subsystem snapshots of the first 120 ticks (M1.2) | 238 ticks (120 with boundaries), 24 s | - |
| `attract_all_demos.txt` | VGA | all five demos (dos_time 00:00:28: 2,0,3,0,3,0,4,1), the high-score/title cycle between them, demo choice by time(); through the demos: walking, jumping, falling, climbing (demo 4), gun, jetpack flight (demo 0, sound 9), shooting monsters (sound 8), monster fire, deaths (demos 1, 3), trophies, scrolling | 11441 ticks, 413.5 s | - |
| `attract_out_of_range_demo.txt` | VGA | dos_time 00:16:55: seed 7002, demo index 5 read from past the 5-entry table, garbage demo on level 3 from the CGA tileset bytes, death, attract mode frozen in `wait_for_input` | 899 ticks, 40 s | - |
| `level1_complete.txt` | VGA | game start from the title, `wait_for_input`, walking, turn-around step, jumps, bumping walls, falling, gems, trophy, door, level-complete corridor, level 2 start | 944 ticks, 34 s | yes |
| `game_over_highscore.txt` | VGA | level 1 as above, then four deaths in level 2's fire (killed tick without a retrace, 300-tick death timer, restart, lives), game over, high-score table, initials, DSCORES.DAV rewritten and compared | 2237 ticks, 66 s | yes |
| `ega_attract.txt` | EGA | mode 0Dh, retrace rate, per-tick plane capture, 40 true 4-plane images | 509 ticks, 32 s | - |
| `cga_attract.txt` | CGA | mode 4, retrace rate, full CGA framebuffer | 509 ticks, 32 s | - |

Not yet in the corpus (open, PORT_ROADMAP M1.3):

- **Live play of levels 2-10.** Scripted play beyond level 1 has to be
  written level by level (level 2 is a maze with deadly weeds; from level 3
  on monsters shoot). Jetpack, gun/shooting and climbing are covered by the
  demos (same game logic, demo input instead of keys), not yet by keys.
- **Warp zones and the level -1 warp** (U-M3). Reachable only from levels
  5, 8, 9, 10 (intended warps; level 5's starts at the tree at the start
  position) and, for the level -1 warp, levels whose top row is open at a
  level edge (level 6: the gems at row 0, columns 85-98, then right past
  x 0x132 at view 80; collision tests return 0 above the playfield). Needs
  the live play above. state-model.md D4 already keeps the level -1 warp
  outside the byte contract.
- Configuration screens (F2 control panel, key/joystick/mouse set-up),
  F1 help, F9 pause, F3 restart, Esc quit: each is entered by a key whose
  tick must be snapped like any other input.
- EGA/CGA live play (the VGA scenarios' times do not carry over: retraces
  are 17% longer, re-snap per mode).
