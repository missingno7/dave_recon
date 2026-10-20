# Nativization ledger

Every dependency of the original program on its historical machine, OS,
runtime or toolchain, mapped to the service it actually provides the game
and to its intended native replacement. A subsystem advances through:

**Recovered** (original implementation reconstructed, EXACT) ->
**Understood** (semantics documented) -> **Readable** (clear native-oriented
source) -> **Native** (no original machine execution) -> **Decoupled** (no
historical memory/OS/hardware assumptions) -> **Verified** (oracle replay) ->
**Complete** (no migration debt).

Historical matching is tracked separately (`docs/dashboard.json`; frozen at
tag `historical-baseline-v1`). Inventory measured 2026-10-20 from `src/*.C`,
`src/asm/*.asm`, `docs/library-map.md`.

## A. Subsystems

| subsystem | original code | state | blocking next step |
|---|---|---|---|
| main loop / tick pipeline | `main` (DAVE.C) | Recovered, Understood (FIDELITY.md section 1) | native fixed-step loop decoupled from retrace |
| player movement / physics | `move_dave` (3,849 B), `update_jetpack`, `scroll_screen` | Recovered, partly Understood | field-level semantics of Dave state bits, jump table (U-G1..G4) |
| monsters / shots / explosions | `move_monsters`, `move_bullets`, `update_explosions`, `spawn_*` | Recovered, partly Understood | monster record fields (U-G5) |
| collisions / items / tiles | `check_collisions`, `pick_up_items`, `tile_at*`, `animate_tiles` | Recovered, Understood (tables named) | -- |
| levels / transitions / warps | `load_level`, `level_complete`, `check_warp_transition` | Recovered, Understood (level-6 warp bug explained) | -- |
| death / restart / game over | `handle_death`, `ask_restart`, `check_high_score` | Recovered, Understood | -- |
| input (keyboard/joystick/mouse/demo) | `process_input`, `get_player_input`, `read_*_input`, `keyboard_isr` | Recovered, Understood | native input sampling at tick boundary |
| demos (record/playback) | `attract_mode`, `demo_*`, demo bank codec | Recovered, Understood, format codec exists | -- |
| high scores / persistence | `check_high_score`, `input_initials`, DSCORES.DAV I/O | Recovered, Understood | -- |
| configuration screens | CONFIG.C | Recovered, partly Understood | -- |
| text / windows / fonts | HARDWARE.C text windows, `DrawChar*` (asm) | Recovered | -- |
| rendering (tiles, sprites, masks, view) | `draw_*` (C) + tiles.asm (60 asm procs total) | Recovered, partly Understood | per-mode blit semantics (U-R1..R4) |
| sound | `PlaySound` etc. + INT 8 driver (lowlevel.asm), SPK bank codec | Recovered, Understood (driver), codec exists | native sound scheduler (requests -> tone timeline) |
| RNG | `srand(time())`, `rand`, asm lagged-Fibonacci `Random` | Recovered, partly Understood | which generator feeds which behaviour (U-S1) |
| resource loading | `load_graphics`, `load_file`, `load_rle_file`, `read_file_far`, RLE | Recovered, Understood, codecs exist | -- |

## B. Machine dependencies -> native services

| dependency (original) | where | game-visible service | native replacement | elimination plan / state |
|---|---|---|---|---|
| VGA retrace polling, port 3DAh | `WaitVBL` (asm), called by move_dave, scroll, transitions | the simulation clock: one tick per retrace (70.086 Hz VGA) | fixed-step simulation clock; presentation decoupled | understand per-mode rates (U-T2); then a `tick()` API |
| INT 10h (modes 3/4/0Dh/13h, DAC load 1012h) | `set_video_mode`, `VideoID` | choice of presentation mode + palette | logical framebuffer per original mode; palette from codec | Recovered/Understood |
| direct video memory A000/A800/B800, EGA sequencer/GC ports 3C4h/3CEh, latches, planes | tiles.asm, lowlevel.asm blitters, `ega_upload_planes` | drawing tiles/sprites/text into the screen; A800 tile cache | operations on an 8-bit indexed logical framebuffer (VGA semantics), CGA/EGA as palette/resolution variants | per-routine algorithm recovery (Phase 4) |
| adapter detection (Wilton VIDEO_ID, INT 10h 1A00h/12h, 6845 probes) | `VideoID`, `detect_hardware` | default video mode | native option, default VGA | trivial; Phase 6 |
| INT 9 keyboard ISR, port 60h, PIC EOI port 20h, BIOS buffer flush 0040:001A/1C | `keyboard_isr`, `install/restore_keyboard_handler` | key-down table `key_down[128]` | platform fills the same logical key table at tick boundaries | Phase 6 |
| INT 16h `bioskey` (24 call sites) | menus, prompts | "is a key waiting / which key" | logical key-event queue | Phase 6 |
| INT 33h mouse | `config_mouse`, `read_mouse_input` | mouse as direction/fire device | SDL mouse mapped to the same logical input | Phase 6 |
| joystick port 201h timing loop | `read_joystick_axes` | analog stick -> thresholds | SDL gamepad axes through the same thresholds | Phase 6 |
| PIT channel 0 reprogramming + INT 8 hook, speaker port 61h, PIT ch2 | lowlevel.asm sound driver | PC-speaker tone sequences with priority | sound scheduler (logical PIT-rate timeline) + synthesizer backend | Phase 4/6; driver semantics Understood |
| DOS file I/O (INT 21h 3Ch/3Dh/3Eh/3Fh/40h/42h via asm; `open/read/close/filelength`) | `read_file_far`, `write_file_far`, `load_file` | load EGADAVE.DAV, DSCORES.DAV, demo save | stdio/SDL file API with explicit little-endian parsing | Phase 6 |
| far/huge pointers (71 far, 17 huge uses), `farmalloc`, segment arithmetic, `movedata` | resource buffers (0x16000-byte work buffer), tilesets, level pointer | large byte buffers | ordinary native arrays/structs owned by resource objects | Phase 5 |
| DS-relative globals at fixed addresses, parallel arrays, overlapping buffers | all units | game state | typed native state structs; layout-dependent quirks reproduced explicitly | Phase 5 (U-M*) |
| 16-bit int arithmetic and wrap-around, signed char | everywhere | exact numeric behaviour | `int16_t`/`uint16_t`/`int8_t` where observable | Phase 5 |
| Borland runtime (C0S, CS.LIB: 59 modules; 29 distinct routines called) | startup, `rand/srand/time`, `itoa/ltoa/ultoa`, `movmem/setmem`, `malloc/farmalloc`, `toupper`, `exit` | C library services | standard C, plus an exact reimplementation of Borland `rand()` (LCG) where results are observable | Phase 6 |
| `time()` (seeds RNG) | `init_game_once`/`load_level` | random seed | injectable seed (fixed in tests) | Phase 6 |
| TCC/TASM/TLINK/LZEXE toolchain, DOSBox | build + oracle | historical build and reference | CMake + modern compiler for the port; DOSBox only for the oracle | the native build never uses them |

## C. Compatibility scaffolding

None in the game. Test-only verification code (never linked into the game):

| scaffold | purpose | removal |
|---|---|---|
| `port/tests/bridge/bridge.c` | imports/exports native state from/to original DGROUP snapshots so native subsystems can be compared with the oracle | permanent TEST tool; must never be used by game/, present/ or platform/ code |

## D. Native code

| native unit | original | state | evidence |
|---|---|---|---|
| `port/game/anim.c` `anim_step()` | `animate_tiles` (DAVE.C, F_332C) | Readable, Native, Decoupled (state part; redraw reported via callback to presentation), Verified on `attract_boundaries` (120 ticks, state changed every tick, whole DGROUP equal) | `tools/native_check.py animate_tiles`, `tests/test_native.py`; mutation (period 9) caught at tick 10, DS 0x615A |
| `port/game/explosions.c` `explosions_step()` | `update_explosions` (DAVE.C, F_18F6) | Readable, Native, Decoupled (XOR erase/redraw as `DRAW_XOR_SPRITE` commands in the original order), Verified on `inv_demos_all` (5,387 ticks, game state changed on 566, whole game view equal) and on `n1_ega_demo2` / `n1_cga_demo2` (819 ticks each, no explosions there) | `tools/native_check.py update_explosions --run build/oracle/demos_all/run1`, `tests/test_native.py`; mutant `update_explosions/mutant` (frame period 12) caught at tick 1174, DS 0x4F98 (actor 0 `.anim`) |
| `port/game/monsters.c` `monsters_step()` | `move_monsters` (DAVE.C, F_2D87) | Readable, Native, Decoupled; `monster.shown_frame` replaces `g_monsters.sprite` (D3), bridge rebuilds the per-mode ids. Verified on `inv_demos_all` (5,387 ticks, state changed on 3,072, monsters fire), sprite ids equal on every tick; on `n1_ega_demo2` and `n1_cga_demo2` (level 4 in modes 0Dh and 4: 819 ticks, state changed on all 819; EGA/CGA sprite ids equal) | `tools/native_check.py move_monsters`, `tests/test_native.py` (`test_move_monsters_sprite_ids`, `NativeMonstersOtherModesTest`); mutant `move_monsters/mutant` (move period 4) caught at tick 1182, DS 0x578A..0x5790 (`.move_count`) |
| `port/game/shots.c` `shots_step()` (+ `shot_draw` = draw_object, `shot_owner_exists` = object_exists, `shot_spawn` = spawn_object) | `move_bullets` (DAVE.C, F_301B) | Readable, Native, Decoupled. Verified on `inv_demos_all` (5,387 ticks, state changed on 1,105: Dave's and the monsters' shots, wall hits, off-screen drops) and the EGA/CGA runs (278 of 819). `shot_spawn` is exercised through move_monsters (monster fire) only; spawn_object is the world worker's (N3) to own | `tools/native_check.py move_bullets`, `tests/test_native.py`; mutant `move_bullets/mutant` (speed 3) caught at tick 2330, DS 0x56F8 (shot 0 `.x`) |
| `port/game/level_probe.c` `tile_attr_at_offset()`, `level_record_byte()` | `tile_attr_at_offset` (F_2D38), `g_level_path` reads | Native; unchecked column / path reads reproduced over the flat 10-record `g_levels` (live map + resources incl. the 24-byte trailers), signed tile bytes through the constant 256-word window around `g_tile_attr` (U-M1 items 2, 3); outside g_levels: 0 (D4); rows outside 0..9 through `row_offset()` (the neighbouring RowTimes100 tables, N2-1), `tile_climbable()` through the same window | used by the three subsystems above; `NativeConstantsTest` checks the window and the monster size window against DAVE.EXE |
| `port/game/world.c` `check_collisions()` (+ `spawn.c` spawn_explosion, `score.c` update_score; shots through N1's `shot_owner_exists`) | `check_collisions` (F_37ED) | Readable, Native, Decoupled (draw commands), Verified on `n3_attract_demos` (6,060 ticks, 4 changing: monster shots and Dave's shots) and `n3_level1_complete` (890 ticks, no change) | mutation `(level + 1) * 100` -> `* 101` caught at tick 1739, DS 0x4C60 |
| `port/game/items.c` `pick_up_items()` | `pick_up_items` (F_3FD5) | Readable, Native, Decoupled, Verified on `n3_level1_complete` (890 ticks, 4 changing: 2 gems, trophy, door) and `n3_attract_demos` (6,060 ticks, 37 changing: gems, gun, jetpack, trophy) | mutation gem value 100 -> 110 caught at tick 107, DS 0x4C60 |
| `port/game/transitions.c` `level_complete()` (+ `level.c` load_level, wait_for_input, draw_actors) | `level_complete` (F_3BA3) | Readable, Native, Decoupled (per-retrace loops, `out->retraces`), Verified on `n3_level1_complete` tick 883 (corridor walk, load of level 2, wait_for_input until Right; native 594 retraces, oracle tick 595 = + move_dave's WaitVBL) and 889 no-change ticks | mutation `x += 2` -> `x += 3` in the corridor walk caught at tick 883; the 10-step-animation mutation of wait_for_input in tests |
| `port/game/transitions.c` `check_warp_transition()` | `check_warp_transition` (F_34CB, level-6 warp bug) | Readable, Native, Decoupled; verified only as "no change" on the 890 + 6060 corpus ticks (no warp in the corpus, U-W2) | -- (needs a warp scenario, e.g. level 3's top-row opening -> level -1, U-O1) |
| `port/game/attract.c` `attract_mode()` (+ `level.c` init_game_state, redraw_screen, show_high_scores; `rng.c` Borland rand) | `attract_mode` (F_09DE) | Readable, Native, Decoupled; time(NULL) is an input (D7, from the oracle's seeds.jsonl). Verified: title -> game start by a key (`n3_level1_complete` tick 1: 602 retraces, oracle 603), title timeouts with demo choice (`n3_attract_demos`: ticks 1, 820, 3145, 3729, 6054 = demos 2, 0, 3, 0, 3; the four high-score + title calls report 2,200 WaitVBL, the oracle tick 2,249-2,250: the rest is WaitSound, timing-exempt), out-of-range demo index 5 (`n3_out_of_range_demo`: native 1200 retraces, oracle 1201) | mutations `srand(100)` -> 101 caught at tick 1; garbage-demo level byte 2 -> 3 caught at tick 1 |
| `port/game/tiles.c` tile_at / tile_attr_at (+ `map_byte`; `row_offset` moved to level_probe.c, N2-1) | F_2C70, F_2CD8 | Readable, Native; built on `level_probe.c` (one flat-read and one g_tile_attr window for both lanes); tile_at's rows 10/11 read RowTimes100's neighbour TileRowOfs (640, 1280) | pick_up_items reads the map through `map_byte`; tile_at/tile_attr_at are move_dave's (N2) |
| bridge: `dgroup_export_levels` | g_tiles, g_levels records | g_tiles is no longer deferred: rebuilt from the level resources (DAVE.EXE's g_levels, `levels.bin`) and `level.index` / `level.pristine_loaded`; identity passes on 12,460 boundary snapshots | `tools/native_check.py identity` |
| `port/game/player.c` `player_process_input()` (+ `handle_menu_key` dispatch as `enum menu_request`) | `process_input` (DAVE.C, F_4A27) | Readable, Native, Decoupled: input is a `struct frame_input` (`port/game/input.h`, settings outside struct game, D6); demo playback reads the demo-bank resource through `game.demo`; the dead recorder block is dropped. Verified on `inv_demos_all` (5,387 ticks), `n2_demos` (11,440: all five demos, 13 Dave shots via `shot_spawn`, 3 jetpack toggles, 8 demo ends), `n2_death` (2,236), `n2_buttons` (882: 10 fire / 9 jetpack release triggers, U-G9 b); presentation ids rebuilt from the pose equal on every tick. Menu keys / demo exit by key are not in the snapshot (BIOS buffer): unverified | `tests/test_native.py` NativePlayerTest; bridge mutant `process_input/mutant` (fire reload 29) caught at tick 34, DS 0xAC; source mutants (reload 31, no jetpack release, SE kept as SE) caught at ticks 34 / 176 / 23 |
| `port/game/player.c` `player_move()` (+ scroll_screen, animate_tick, draw_dave / erase_dave, draw_actors, spawn_explosion) | `move_dave` (DAVE.C, F_1D16) | Readable, Native, Decoupled: drawing as `DRAW_SET_DAVE_SPRITE` / `DRAW_DAVE` / `DRAW_ERASE_DAVE` / `DRAW_LEVEL_VIEW` / `DRAW_XOR_SPRITE` (draw_actors, spawn_explosion, tile_at / tile_attr_at: the world lane's single definitions), sound as requests (`SOUND_STOP/PAUSE/RESUME` for the driver calls), retraces counted per wait (`retrace()`, one boundary per WaitVBL for D2). `dave.pose`/`pose_frame` replace `g_dave_sprite`/`g_dave_mask` (D3). Verified on the same four runs (19,945 ticks; walk, jump, fall, climb 148 ticks, jetpack 570 ticks, 18 scrolls, 2 8-bit y wraps, 7 tile deaths); retraces equal `frames_since_prev` on all 19,917 play/demo ticks without a level change (38 of them with 0 or 16 retraces); PlaySound requests a subsequence of the tick's sound log | bridge mutant `move_dave/mutant` (throttle 2) caught at tick 3, DS 0x5794; source mutants: no 8-bit y wrap (demos_all tick 4401, DS 0x56ED), no turn-around step (n2_buttons tick 790), explosion y+2 (n2_death tick 920), climb/jetpack anim periods (n2_demos ticks 9083 / 2955) |
| `port/game/player.c` `player_update_jetpack()` | `update_jetpack` (DAVE.C, F_1780) | Readable, Native, Decoupled. Verified on the four runs (state changed on 570 n2_demos / 190 demos_all ticks, 36 fuel units). The fuel-out branch (fuel 0: state & 0xE0 \| 8, icon, sound 2) is in no corpus tick: unverified | bridge mutant `update_jetpack/mutant` and source mutant (fuel period 14) caught at n2_demos tick 2969, DS 0x6154 |
| `port/game/player.c` `player_handle_death()` | `handle_death` (DAVE.C, F_15A5) incl. its `wait_for_input` | Readable, Native, Decoupled; the closing wait is the world lane's `wait_for_input` (level.c, polled through `struct world_io`, one `frame_input` per poll), start positions through `level_start_position` / `warp_start_position` (shared with load_level / the warp). Verified on the four runs: n2_death covers the 300-tick timer, 3 restarts (21 retraces each) and the game over (lives -1, map restored); the warp-zone restart branch is in no corpus tick: unverified | bridge mutant `handle_death/mutant` and source mutant (timer step 2) caught at n2_death tick 920, DS 0x6546; restart facing left caught at tick 1219, DS 0x5740 |
| `port/platform/input_map.c` `input_from_keyboard()` | `read_keyboard_input` (HARDWARE.C, F_63AF) | Native, pure settings decoding (bindings `g_key_scans`): the one implementation, used by the bridge's world input (world_io.c) for every waiting loop and process_input, and by the future platform layer | exercised by every process_input / handle_death tick of `n2_death` and `n2_buttons` |
