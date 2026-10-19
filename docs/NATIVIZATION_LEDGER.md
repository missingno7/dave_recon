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
