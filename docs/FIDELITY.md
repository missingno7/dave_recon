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
- **Emulator finding 2 (2026-10-20): the host's load still reaches the VGA
  retrace phase.** With the host busy during DOS boot (concurrent oracle
  runs, or ~90 extra `on_exec` triggers checked on every instruction) the
  game's first `WaitVBL` exit came at 3489-3497 ms instead of 3498.8-3501.2
  ms (quiet runs; EGA 3499.648 and CGA 3506.792 never varied), offsetting
  every later retrace and moving snapped keys across tick boundaries. The
  oracle now arms every hook and port watch at 3000 ms (when DAVE is typed;
  nothing of the game runs before), arms the draw hooks at 3490 ms, and
  restarts a run whose first `WaitVBL` exit falls outside the quiet window
  (`PHASE_WINDOW`, up to 12 tries; summary.json `startup_phase_ms`,
  `attempts`). Under the draw hooks a video mode set later in the run can
  still shift the phase (UNDERSTANDING_LEDGER U-O3).
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
- Pinned keyboard layout: `[dos] keyboardlayout=us`. The default `auto`
  follows the HOST: on a Czech (QWERTZ) Windows host the DOS keyboard layer
  turned the Y key (scan 15h, correctly set in `key_down[]`) into BIOS key
  2C7Ah ('z'), so every "Y or N" prompt ignored a scripted `y`
  (found 2026-10-20 with `demo_key_exit.txt`: F3 -> Y froze the game in
  `ask_restart`). Letters other than y/z were unaffected, so the earlier
  corpus results stand.
- Scenario options: `duration`, `png_every`, `boundaries <n>` (M1.2),
  `video vga|ega|cga` (machine svga_s3 / ega / cga; the game's `VideoID`
  then picks mode 13h / 0Dh / 4), `dos_time HH:MM:SS`, `ega_planes <n>`,
  `retraces <n>` (M1.6), `draws <n>` (M1.6, below), and
  `<ms> key|keydown|keyup <mapper name>`.
- Captures, per **game tick** (hit of `main`'s loop head, cs 0x0283):
  - the complete live DGROUP (DS 0x0000-0x9F20), raw (`ticks.bin`) and with
    named fields decoded (`ticks.jsonl`, incl. `keys_down`, the scan codes
    set in `key_down[128]`);
  - the video memory: VGA A000:0000 64000 bytes; CGA B800:0000 16 KB; EGA
    A000:0000 8000 bytes of the bit plane the graphics controller's read map
    selects at that instant (a CPU read of planar memory sees one plane; in
    practice plane 0, which every EGA blitter leaves selected);
  - the number of retraces since the previous tick (`frames_since_prev`,
    elapsed retrace periods) and, with a `retraces` capture, the number of
    `WaitVBL` calls since the previous tick (`waitvbl_since_prev`; they
    differ when a frame's work takes longer than a retrace: a CGA scroll
    makes 16 calls while 31 periods elapse, U-P1);
  - the BIOS keyboard buffer (`bios_head`, `bios_tail`, `bios_buffer` =
    0040:001E..003D hex, `bios_keys` = the pending keys oldest first), i.e.
    what `bioskey(1)` / `handle_menu_key` sees.
- Per tick, at the input read itself (`keys_at_read.jsonl`): `key_down[]`
  dumped at process_input's `call get_player_input` (cs 0x4844), with its
  time and whether it equals the tick-head table. Scripted key events reach
  the emulated keyboard 0.5-1 ms late and can land between the tick-head
  snapshot and this read (native replay finding at n3 tick 210), so a replay
  takes its per-tick input from here.
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
- **Draw-order capture** (`draws <n>`, M1.6, state-model D1): an `on_exec`
  hook at the entry of every drawing routine of the original
  (`oracle.py DRAW_ROUTINES`, addresses from docs/semantic-inventory.json)
  dumps `ss:sp` (near return address + up to 5 argument words), plus the
  DGROUP variables a few routines draw from; the hits of all hooks and the
  `WaitVBL` exits are merged by emulated time into `draws.jsonl` (section 6).
  The hooks are armed at 3490 ms, just after the first title tick head: armed
  at 0, the ~90 extra per-instruction triggers slowed the host during DOS
  boot and DAVE's start-up mode set enough to shift the VGA retrace timeline
  by 4-10 ms per run, and level1_complete's keys crossed tick boundaries
  (not equivalent); armed at 3490 the timeline equals a run without hooks
  (tick 2 at 12090.35 / 12091.35 ms vs 12089.3-12090.4) and the contract
  holds. The first title redraw (< 4 ms after tick 1's head) is therefore not
  in the stream.
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
  Events inside a gap of more than 1.5 retraces between two `WaitVBL` exits
  (a prompt blocking in `bioskey(0)`, e.g. the F1 help pages) are left where
  they are: those prompts read the BIOS buffer, and moving several events of
  one gap to its middle collapsed their order (title_popups' three help-page
  spaces landed on one millisecond).
- **Scripted routes** (`tools/route.py`, `tools/route_sim.c`): see section 5.

## 3. Equivalence contract (as implemented in `compare_runs`)

Two runs are equivalent when:

| level | compared | rule |
|---|---|---|
| gameplay state | per-tick DGROUP | byte-exact, excluding DS [0x1384,0x1392) (INT 8 driver phase: TickDivide, TickCount, TimerRate, SoundPtr, SoundPriority, saved copies) |
| per-retrace state | DGROUP + key table at every `WaitVBL` exit (when captured) | byte-exact (same exclusion), per tick, for every tick whose interval is under the timing rule |
| timing | retraces between consecutive ticks | exact, except the interval after a high-score tick (game_state 2: a demo ended; show_high_scores(1) with WaitSound and the title in one pass) or a title tick (game_state 3), and the interval ending at a title tick (game over: high-score table and initials) |
| input | key table at process_input's read of every tick (`keys_at_read`); BIOS key buffer at every tick head | exact |
| WaitVBL calls | `waitvbl_since_prev` (with a `retraces` capture) | exact, same exemption as timing |
| draw order | `draws.jsonl` per tick: routine, arguments, caller, extra fields, WaitVBL positions (when captured) | exact; inside timing-exempt intervals without the WaitVBL records |
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
Widened again (oracle lane, same date) to the interval after a game_state 2
tick: when a demo ends, the next pass shows the high scores with
`WaitSound`, the title and starts the next demo, and n3_attract_demos'
tick 821 measured 2250 vs 2249 retraces in two runs (attract_all_demos had
passed by chance). A run's last tick may also be cut by the run's end in one
run and not the other (per-run phase): one extra tick head within 1.5
retraces of `duration` is not a difference.

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
| `title_popups.txt` | VGA | every menu key from the title, each left unchanged: F1 help (3 pages; again with Esc), F2 control panel (cursor moved, Esc), F3 restart -> Y (no effect on the title) and -> N, F9 pause / F9, Esc and F10 quit prompts -> N; then the title timeout and demo 1 | 570 ticks, 40 s | yes |
| `demo_key_exit.txt` | VGA | a non-menu key ends demo 1 into a live game on level 1; F9 pause, Esc -> N, F1 -> Esc and F3 -> Y during play (back to the title); a key on the title starts a new game | 985 ticks, 46 s | yes |
| `levels_1_to_3.txt` | VGA | live play of levels 1-3 (routes planned with tools/route.py): level 2's maze, trophy and door; level 3 with the gun, shooting (two monsters killed), jetpack + trophy, flight to the door; level 4 start | 5213 ticks, 109 s | yes |
| `jetpack_fuel_out.txt` | VGA | levels 1-2, level 3 to the jetpack, then hovering 900 flight ticks until the tank is empty (sound 2, state 0x21 -> 0x28), the fall and landing | 6321 ticks, 118 s | yes |
| `warp_zone_level5.txt` | VGA | levels 1-4 (level 4: jetpack needed for the trophy), level 5: the U-G9 (a) multi-bit states (0x2A climb + fall on a jump's last step, then 0x26, 0x32), the tree climbed above row 0, the warp tube into the warp zone (level 2's map), the zone's trophy and door, the return to level 5 | 14181 ticks, 258 s | yes |
| `warp_zone_death.txt` | VGA | as warp_zone_level5 to the warp, then a death in the zone (spikes at the shaft's bottom), the death timer, handle_death's warp-zone restart (lives 2), play on in the zone | 12550 ticks, 228 s | yes |

Further scenarios of the native lanes (each EQUIVALENT under `--repeat 2`
with the oracle of 2026-10-20, headers in the files): `n1_ega_demo2` /
`n1_cga_demo2` (now with `retraces`), `n2_buttons`, `n2_death`,
`n2_demos`, `n3_level1_complete`, `n3_attract_demos`,
`n3_out_of_range_demo`, `inv_demos`, `inv_demos_all`.

**Scripted routes (tools/route.py).** Long routes are planned per tick, not
written in milliseconds: `route_sim.c` chains the native port's pipeline
calls (port/game, read-only) from one tick-head DGROUP snapshot of an
oracle run; `route.search` is a best-first search (optionally A* toward a
target, a time bucket so places can be revisited when monsters have moved)
over macro moves from decision states (walk n ticks, jumps N/NE/NW with air
control, climbing, jetpack flight and toggles, Ctrl taps when Dave has the
gun), pruning deaths; built-in demo input can be replayed live
(`route.demo_inputs`). `route.plan_events` turns the per-tick plan into
key events half a retrace before each tick head (a wait the plan does not
end by a held direction gets its key just before the poll, and that key is
still held at the next read); the scenario is then run, `--snap`ped and
repeated. The original is the judge: `route.plan_check` compares the plan
with the run tick by tick (every segment of the corpus followed its plan
exactly), and `python tools/route.py check RUN` replays a run's own key
tables through the simulator (4,329 live ticks of levels 2-4 agree).

Not yet in the corpus (open, PORT_ROADMAP M1.3):

- **The level -1 warp** (U-M3). Level 3's top-row opening (columns 72-74)
  is NOT a route: it opens only into a pocket (row 1 columns 73-75 and the
  row-2 gem corridor 74-97) closed below by row 3's wall, reachable only
  from above the screen (exhaustive jetpack search from level 3's jetpack).
  The candidate is level 6 (gem block entered at row 4 column 84, row 0
  open at columns 85-98, then right past x 0x132 at view 80). Level 6 is
  reached in the simulator (levels 1-5 completed, see UNDERSTANDING_LEDGER
  "Oracle lane, second pass"), but its bottom corridor holds three monsters
  that shoot, the gun is reachable only with the jetpack, and the planner
  has not yet found a route through them to the gem block.
- **Live play of levels 6-10**, the warp zones of levels 8, 9 and 10, the
  ending after level 10 (U-G8). The planner reaches level 6; levels beyond
  need the monster handling above.
- Control-panel CHANGES (video mode switch, sound off, key redefinition,
  joystick/mouse set-up): only entering and leaving unchanged is covered.
- EGA/CGA live play (the VGA scenarios' times do not carry over: retraces
  are 17% longer, re-snap per mode).
- The draw capture in scenarios with video mode sets after the title
  (F2 / F9): its hook load shifted the retrace timeline (U-O3).

## 6. Draw-order capture (M1.6, state-model D1)

`draws <n>` in a scenario (hooks armed at 3490 ms, section 2) writes
`draws.jsonl`: one record per call of a hooked drawing routine and per
`WaitVBL` exit, in execution order (merged by emulated time; every hook is a
distinct instruction, so no two records share a time).

| field | meaning |
|---|---|
| `seq` | position in the stream |
| `tick` | tick heads at or before the call (the call belongs to that tick's pipeline pass) |
| `retrace` | `WaitVBL` exits since that tick head (D2: the retrace the call precedes) |
| `routine` | original routine (`WaitVBL` records have only seq/tick/retrace) |
| `args` | its stack arguments, signed 16-bit (C convention: first argument at ss:sp+2) |
| `caller` | the near return address (cs offset) |
| `top` | the caller is not inside any hooked routine |
| `op` | the output.h op, set when the routine has one AND its caller is not inside a routine that has one (a `print_string` inside `draw_control_panel` counts; a `draw_text_window` inside `draw_centered_window` does not) |
| extras | `draw_dave`: `x`, `y`, `sprite`, `mask` (g_player_x/y, g_dave_sprite/mask at the call); `DrawLevelView`: `level`, `scroll`; `print_string`/`print_int`/`print_long`: `cursor` = [g_text_x, g_text_y, g_text_left], `xor_mask` (print_string); `print_string`: `text` (the string, for pointers into initialised data) and `chars` (the characters its DrawChar calls drew: covers stack buffers) |

To compare with the native stream (port/game/output.h) take the records
with `op` set, in order, and map:

| output.h op | original routine (entry, cs) | arguments compared | inner routines (op None) |
|---|---|---|---|
| DRAW_TILE | `DrawTile` (tiles.asm, 0x90D6) | col, row, tile | (DrawTileAt, not hooked) |
| DRAW_XOR_SPRITE | `xor_sprite` (DAVE.C, 0x19D6) | x, y, per-mode sprite id (the bridge maps (set, index) to it, D3) | DrawXorCGA/EGA/VGA |
| DRAW_PIC | `draw_tile` (DAVE.C, 0x1984) | x, y, per-mode pic id (PIC_DIGIT / PIC_TITLE_ANIM resolved per mode) | DrawPicCGA/EGA/VGA |
| DRAW_ERASE_DAVE | `erase_dave` (0x1A28) | - | restore_background, RestoreUnder* |
| DRAW_DAVE | `draw_dave` (0x1A6A) | x, y from the extras | save_background, SaveUnder*, DrawMasked* |
| DRAW_SET_DAVE_SPRITE | (an assignment, not a call) | compare with `sprite`/`mask` of the next `draw_dave` record | - |
| DRAW_LEVEL_VIEW | `DrawLevelView` (0x8CDA) | level, scroll extras | - |
| DRAW_VIEW_BORDERS | `DrawViewBorders` (0x9011) | - | - |
| DRAW_SET_VIDEO_MODE | `set_video_mode` (HARDWARE.C, 0x6B64) | mode | CacheEGATiles (called by redraw_screen next to it in EGA: op None) |
| DRAW_TEXT_CURSOR / DRAW_TEXT_XOR | (assignments) | compare with `cursor` / `xor_mask` of the next print_string | - |
| DRAW_PRINT_STRING | `print_string` (0x6E71) | text (`text`, or `chars` for stack buffers) | DrawChar |
| DRAW_CENTERED_WINDOW | `draw_centered_window` (0x6CF1) | w, h | draw_text_window |
| DRAW_HISCORE_ROW | four `print_string` calls of `show_high_scores` on stack buffers (score digits, initials, level, "\n\n\r") | `chars` | DrawChar |

Hooked without an op yet (they appear with `op` None at top level):
`draw_masked_sprite` (help screen pictures), `DrawChar` from
`wait_key_cursor` (the blinking prompt cursor) and the control panel,
`DrawPic` (control panel), `draw_text_window` / `clear_text_window` /
`open_window_anim*` / `draw_control_panel` (control panel and windows),
`print_int` / `print_long`.

Verified reproducible (2 runs each, `draws.jsonl` equal per the contract):
attract_boundaries (3,139 records over 238 ticks), level1_complete (5,791
records over 944 ticks), title_popups (help, control panel, prompts).
