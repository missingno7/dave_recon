# Understanding ledger

Open semantic questions, each with the evidence needed to close it. Status:
**open** / **partial** (behaviour or representation known, not both) /
**closed** (moved to the "Closed" list with its evidence). Names in the
recovered sources are evidence-based; a name marked *tentative* in a source
header is listed here until proven.

Baseline inventory (2026-10-20): 90 C functions (all named), 60 assembly
procedures (named, with census ids), 209 named globals, 6 unreferenced BSS
holes (`g_unused_*`), every far-data segment and the level array decoded by
exact codecs.

## Open

### Timing (T)
- **U-T1** How many retraces each non-gameplay sequence waits (death,
  warp tube, level transition, scroll): enumerate per call site of
  `WaitVBL`; verify with oracle `frames_since_prev`.
- **U-T2** Refresh rates of the CGA (mode 4) and EGA (mode 0Dh) paths in
  the original hardware, i.e. the simulation rate in those modes. Evidence:
  oracle runs with machine=ega/cga and period measurement; hardware docs.
- **U-T3** Title-screen timeout: which timer it counts (BIOS tick count vs
  the game's INT 8 rate) and its exact length. *Partial (2026-10-20):* it
  counts **retraces**, not a timer: `attract_mode` state 3 runs 200 x 6
  `WaitVBL` = 1200 retraces (key/fire polled every 6), plus the mode sets
  and redraws around it; the oracle sees 1201 or 1202 retraces from the
  title tick to the first demo tick. Still open: the source of that +-1
  (a hypothesis: an INT 8 handler overlapping a retrace edge so `WaitVBL`
  misses one). FIDELITY.md's "measured in real time" holds only for the
  high-score screen before later title cycles, whose `WaitSound` waits on
  the PIT-driven sound.

### Gameplay (G)
- **U-G9** Confirm with scripted oracle scenarios two behaviours read from
  the code but not yet in the corpus: (a) several movement bits at once
  (grabbing a ladder on a jump's last step sets 0x02 and 0x08, then the
  branch order 0x04, 0x08, 0x10, 0x02, 0x01 decides; the 4 attract demos
  only show one-hot states); (b) fire / jetpack buttons act on **release**
  (or every 30 held ticks), `process_input`'s `g_fire_repeat` /
  `g_jetpack_repeat` scheme. Needs keyboard scenarios (M1.3).

### Rendering (R)
- **U-R1** Exact draw order per tick, and which routines draw to the visible
  page vs back buffers (save/restore-under semantics).
- **U-R2** EGA tile cache at A800h (latched copies): purpose and exact
  effect, so it can be expressed as a plain blit.
- **U-R3** CGA sprite "unread tails" (2,713 bytes) and sprite header misreads
  caused by the duplicated VGA-tileset byte at offset 0xFF00 (resources
  147-157): visible on screen?
- **U-R4** XOR font mask (DS 0x1392) usage and the cursor/text effects.
- **U-R5** The title animation counter `j` in `attract_mode` is an
  uninitialised stack word: its starting value (the phase of the two
  animated title tiles drawn with `(j & 3) + 6`) is whatever the previous
  calls left at that stack slot. Determine it (oracle framebuffer of the
  title, or the stack history) so the native title screen can match.

### Sound (S)
(U-S1, U-S2 closed 2026-10-20.)

### Memory/layout (M)
- **U-M3** The bad warp to level -1 (see U-M1 in the closed list): (a)
  which levels actually let Dave get above the top row at the far left
  (view 0, x < 2) or far right (view 80, x > 0x132) -- every level whose
  warp target is 0 qualifies by the code (1-based 1, 2, 3, 4, 6, 7; row 0
  is open near an edge in levels 1, 6 and 7), only level 6 is documented;
  (b) observe the course predicted from the code with a scripted oracle
  run: Dave frozen in state 0x08 (not alive), the death timer running from
  0 through 65536 ticks (about 15.6 minutes), the four "monsters" of
  `g_level_monster_init[-1]` stepping over DS 0x123A.. with no 0xEA,
  collisions against DS 0x133A..0x1721 and a view drawn from level 8's map.
  Then decide whether the port reproduces it (it depends on the BIOS INT 8
  vector and the asynchronous sound-driver bytes, row 0 columns 70..88 of
  that map) or documents it as out of the equivalence contract.

### Data provenance (D)
- **D-1** Over-read bytes after the RLE streams (CGA 1 byte, VGA 22 bytes
  that look like x86 code), demo post-terminator bytes, sound-name tails:
  origin (encoder memory contents?). No behavioural effect expected.
- **D-2** Whether the data-only module and the far blobs came from C files
  or a bin-to-OBJ tool (not decidable from bytes; no behavioural effect).

### Oracle naming corrections
- **N-1** DS 0x9EC2 is the input module's demo record/playback mode, *not*
  the attract flag: during attract demos `game_state` (0x00AA) = 1 while
  0x9EC2 = 0 (oracle trace 2026-10-20). Rename in the native state model.

## Closed (with evidence)

- **DS 0x615A** = the animated-tile period counter: `animate_tiles` steps
  every animated tile one frame when it counts down to 0 and reloads it with
  10 (`init_game_state` also loads 10). The external RE's "levels_left" is
  wrong. Evidence: source; native `anim_step` equivalent over 120 oracle
  ticks, and a period-9 mutation diverges at DS 0x615A on tick 10.

Closed 2026-10-20 by the semantic inventory (M2.1/M2.2). Every entity's
purpose, status, evidence and mechanical relations: `docs/semantic-inventory.md`
(`tools/semantic_inventory.py --check`). Oracle evidence:
`tools/semantic_experiments.py` on `tests/oracle/inv_demos.txt` (6,230 ticks,
boundaries for 2,000) and `inv_demos_all.txt` (5,388 ticks, all with boundaries:
the attract demos on levels 2, 9, 3, 5); its first check shows that every DGROUP
byte any subsystem changed (111,065 over 5,387 ticks) lies in an object whose
static writer set (call closure) contains that subsystem.

- **U-G1** Dave state word `g_dave_state` (DS 0x6156). Bits: 0x01 jetpack
  flight, 0x02 climbing, 0x04 walking (on the ground), 0x08 falling, 0x10
  jumping, 0x20 alive (controllable; everything that hurts or acts checks
  it), 0x40 killed; 0x80 is never set. Movement bits are one-hot in practice;
  each transition clears the bit of the branch that runs (`& 0xFB`, `& 0xF7`,
  `& 0xEF`, `& 0xFD`, `& 0xFE`) or all of them (`& 0xE0`: jetpack on,
  fuel out, death). Death has three forms: deadly tile -> `state & 0xE0 |
  0x40` (still alive; the next `move_dave` turns it into 0 and spawns the
  explosion), monster touch -> `state & 0xC0` (0), monster shot -> 0x40
  (alive bit clear; the 0x40 is inert). Level start / respawn load 0x24 or
  0x28 (`g_level_flags`), a warp arrival 0x28. Writers (mechanical):
  move_dave, process_input (jetpack on/off), update_jetpack (fuel out),
  check_collisions, load_level, handle_death, check_warp_transition.
  Oracle: every state change at a subsystem boundary is one of these
  (`dave_state transitions`: 14 kinds, e.g. 0x24->0x30 x36, 0x30->0x21
  jetpack on, 0x28->0x60->0x00 tile death). Multi-bit states are possible
  but unobserved: U-G9.
- **U-G2** Jump table `g_jump_dy` (DS 0x00BA): 0, -3, 11 x -2, 7 x -1, 7 x 0,
  7 x +1, 10 x +2, +3, then 0x80 = switch to falling: Dave rises 32 px (two
  tiles) and is 2 px above the take-off height when the fall starts; one
  step per 2 ticks. Every step is `y = (y + t) & 0xFF`: y is 8-bit in the
  movement code. "Speed throttle DS 0x5794" = `g_death_pause`, misnamed: it
  is decremented every alive tick and reloaded with 3 after a move, so Dave
  moves every 3rd tick walking, every 2nd jumping or climbing, every tick
  falling or flying. Oracle: 1,334 jump steps all `(y + g_jump_dy[pos]) &
  0xFF` (2 of them wrap: the level-3 demo jumps through the top, y 0 -> 254
  -> 0); move periods 3 / 2 / 2 / 1 / 1 for walk / jump / climb / fall /
  jetpack over 2,624 moves (`movement throttle`).
- **U-G3** DS 0x0118 = `g_level_flags[10]`, Dave's initial state per level
  (0x24 alive+walking; 0x28 alive+falling for 1-based levels 4, 7, 9);
  read by load_level and handle_death only. The "102 refs together with
  0x6156" is the external RE conflating it with the state word it seeds.
- **U-G4** DS 0x6150 = `g_anim_frame`, Dave's 4-frame animation index
  (walk, climb, jetpack, the between-levels walk), stepped when the
  countdown `g_anim_delay` (DS 0x6548; 2 walking/climbing, 4 flying) runs
  out; oracle: values 0..3 only. (0x615A: see above.)
- **U-G5** Monsters `g_monsters` (DS 0x5742, struct of 10 arrays x 4):
  active; x in VIEW pixels (scrolling shifts it by 16 per column, respawn
  and warp re-base it); y; path_pos, an unsigned byte index into the
  level's 256-byte path, +2 per step, reset at 0xEA; reload (fire period);
  sprite id (derived: level, frame, video mode); anim_count 2..1;
  anim_frame 0..3; fire_count (counts down only while the monster is at
  0 <= x < 0x154 with no own shot alive); move_count 5..1 (one path step
  per 5 ticks). Init block `g_level_monster_init` (DS 0x0496, 10 x 80 B):
  only active, x (level pixels), y, path start, reload are used; load_level
  overwrites the rest (random frame from rand()). Oracle: 1,683 steps
  match the path bytes exactly (`monster records ...`).
- **U-G6** Shots `g_shots` (DS 0x56F6, 5 x 14 B): active, x (view px), y,
  dir 0 left / 1 right, frame 0..3, kind 0 monster / 1 Dave, id = owner
  (monster i+1, Dave 5). Dave's shot is dropped off-screen, monster shots
  fly on until a solid tile; one countdown for all shots. Actors
  `g_actors` (DS 0x4F8E, 6 x 0x13A B) = explosions: active, x, y, frame
  0..3, life (110 ticks), anim (13-tick frame countdown), type (written,
  never read); bytes 14..0x139 are never referenced (oracle: all zero
  throughout). Field-level readers/writers in the inventory.
- **U-G7** `spawn_explosion` / `update_explosions` are right: the actors
  only ever show sprite set 0, are spawned for Dave (type 5, arming the
  300-tick death timer) and for killed monsters together with sound 8,
  whose SPK name is "explosion" (tools/sounds.py).
- **U-G8** `level_complete`'s border path: 55 positions; entry 47 is first
  the bottom-left corner (0, 9), then overwritten by the left column's
  (0, 8). Observable effect: in the ending the chasing light skips the
  bottom-left corner tile, which stays the static border tile 10. Code
  only (the ending is not in the oracle corpus).
- **U-S1** RNG: only Borland `rand()` is used (Seed = Seed * 0x015A4E35 + 1,
  rand = (Seed >> 16) & 0x7FFF, DS 0x4BB6). `attract_mode` seeds it with
  `srand(time(NULL))` (low 16 bits of the time) and draws one number to pick
  the demo; `load_level` re-seeds with `srand(100)` and draws one number per
  animated tile (start frame) and 4 for the monsters (start frame), so all
  in-level randomness is the same on every load. The asm lagged-Fibonacci
  `InitRnd`/`Random` is dead code (no caller; the binary walk only "reaches"
  it by running past Int8ISR's IRET). Oracle: after each of 5 level loads
  the seed is LCG^(n+4)(100) and the tile phases and monster frames equal
  the predicted outputs, up to the one step the first tick may already make
  (`rand seed ...`). Consequence: `rand()` returns
  32767 first for 16-bit seeds 3501 and 7002 only, see U-M1.
- **U-S2** Sound driver: `PlaySound(n)` starts sound n when its priority >=
  the playing one's (StopSound and the end marker reset the priority to 0);
  the directory's rate m (5..25 for sounds 1..12) sets PIT channel 0 to
  65536/m (18.2 m Hz) and the ISR chains the BIOS every m interrupts, so the
  BIOS clock keeps 18.2 Hz; each interrupt outputs one u16 divisor on PIT
  channel 2 (0 = rest, 0xFFFF = end). PauseSound saves pointer, priority,
  multiplier, count and rate and stops; ResumeSound restores them all. A
  rate <= 1 would leave the saved rate stale, but no game sound has one.
  Evidence: lowlevel.asm (EXACT), tools/sounds.py directory.
- **U-M1** Layout-dependent behaviours, enumerated (code + bytes of the
  specimen):
  1. *Warp to level -1*: `check_warp_transition` loads level
     `g_warp_target_level_plus1[l] - 1` = -1 for every level without a warp.
     Then load_level reads `g_level_flags[-1]` = DS 0x0117 = 0 (state 0, then
     0x08 after the warp: Dave is not alive), the monster block at DS 0x0446
     (inside `g_sprite_sets`: active {57, 58, 59, 58}, x {75, 77, 79, 77}, ...),
     the path at DS 0x123A (CONFIG.C strings; no 0xEA, so path_pos runs on
     through memory), and makes `g_level` = DS 0x133A: the collision map is
     the asm modules' data and the VGA palette (rows 0-1 include the dead RNG
     tables, the sound driver's variables, the saved INT 8 vector and XorMask;
     rows 2-9 the tile row tables and palette). DrawLevelView instead reads
     by level number: `LevelOfs[-1]` = the last bytes of the unreferenced
     'Trouble loading tileset!$' = 0x2421, i.e. level 8's map from row 2,
     column 89. Monster sprite ids come out as the jetpack set in all three
     modes. Course and reachability: U-M3.
  2. *Collision probes*: `tile_attr_at`/`tile_at` columns are not
     range-checked (column 100 = the next row's first tile; on row 9 the next
     record's path); `tile_at` accepts rows 10-11 (past the map);
     `tile_attr_at_offset` checks nothing (off-screen monster shots probe
     outside the view, columns < 0 reach the previous row or the path bytes).
     Observable only at the extreme right edge / bottom rows / for shots that
     left the screen; all levels have solid borders there, so no corpus tick
     shows it.
  3. *Signed tile bytes*: `g_tile_attr`/`g_tile_climbable` are indexed with
     signed chars; every real map byte is 0..52, so only level -1 leaves the
     tables.
  4. *Demo choice*: `rand() * count / 32767` is 5 when rand() returns 32767,
     reading `offsets[5]` = demo 0's first two bytes = 0x2002, beyond the 4,368
     -byte demo segment (into the CGA tileset): a garbage demo. Happens only
     when the title times out with time() & 0xFFFF in {3501, 7002}.
  5. *Random tile phase*: `rand() * frames / 32767` = frames for rand() 32767
     would start a tile one past its cycle; with seed 100 rand() never returns
     32767 within the <= 88 draws a level load makes: unobservable.
  6. *Table terminator*: `g_anim_tiles[n + 1].count = 0` could write past the
     200 records; the most animated tiles in a level is 84 (level 2): safe.
  7. *High-score width*: the in-memory entry keeps a 16-bit score (and
     init_game_once decodes the digits in int arithmetic), so a stored score
     >= 65536 is beaten by any score > stored - 65536; the file keeps 5 digits.
  8. *Control panel grid*: `detect_hardware` writes `g_panel_avail[0][5..9]`,
     which is row 1 (sound); the cursor loops stop at column 0, which every
     row has: in bounds.
  9. *8-bit y*: see U-G2 (jumping through the top wraps y to 240..255; the warp
     test then needs y < 16 on the way down).
- **U-M2** The 6 BSS holes (`g_unused_654a`, `_6558`, `_65da`, `_85fe`,
  `_8a04`, `_8a0c`) are unused: no source reference (inventory relations)
  and no DGROUP operand inside them in the binary sweep
  (docs/data-layout.json); inventory check `unused_holes_unreferenced`.

- **g_levels** = DGROUP:0x173A, 10 x 0x500 records (256-byte monster path,
  10x100 tiles, 24 unread bytes); level-6 warp reads level index -1 = DS
  0x123A. Evidence: docs/data-layout.md; exact codec tools/levels.py.
- **Simulation clock** = vertical retrace (one `WaitVBL` per tick in
  `move_dave`; 70.086 Hz in VGA). Evidence: source + oracle (14.27 ms/tick).
- **Sound is asynchronous** to the game loop (INT 8 driver on its own PIT
  rate); the game issues `PlaySound(n)` requests. Evidence: lowlevel.asm +
  oracle (driver variables vary with PIT phase, game state does not).
- **Video mode choice**: adapter detection -> 1 CGA / 2 EGA / 3 VGA;
  `set_video_mode` sets modes 4 / 0Dh / 13h (+ DAC palette load).
- **Tileset compression** = the game's own RLE encoder (0x7F41), proven by
  exact re-encoding.

## Oracle corpus lane additions (2026-10-20)

Appended by the oracle-corpus worker (M1.3/M1.4/M1.6); evidence is the
scenario corpus in `tests/oracle/` (all EQUIVALENT under `--repeat 2`) and
docs/FIDELITY.md sections 1 and 5.

### Closed (with evidence)

- **U-T2** Refresh rates: EGA mode 0Dh 16.6897 ms (59.92 Hz), CGA mode 4
  16.6880 ms (59.92 Hz), VGA mode 13h 14.2689 ms (70.08 Hz), mean over the
  play/demo ticks (`summary.json` `retrace_ms_mean`; ega_attract.txt,
  cga_attract.txt, attract.txt). These are DOSBox-X's models of the real
  200-line EGA/CGA timing (14.318 MHz / 912 / 262) and VGA (25.175 MHz /
  800 / 449); the simulation runs 14.5% slower on EGA/CGA.
- **U-T3** (completes the partial entry above) The title loop is 1200
  `WaitVBL`; the +-1 retrace seen earlier was the emulator, not the game:
  DOSBox-X's vertical-timer drift compensation shifted the retrace timeline
  by whole frames with `frameskip=0` (FIDELITY.md section 1). With the
  pinned `frameskip=1` the title tick interval is the same in every run
  (VGA 1201 retraces). So the uninitialised counter `j` (U-R5) is not the
  cause: it only selects the tile drawn, and the title framebuffers are
  byte-equal across repeats (U-R5 itself stays open: its value is
  reproducible but not yet derived).
- **Key bindings (default `g_key_scans`, DS 0x1310)**: N 0x48 Up, NE 0x49
  PgUp, E 0x4D Right, SE 0x51 PgDn, S 0x50 Down, SW 0x4F End, W 0x4B Left,
  NW 0x47 Home, fire 0x1D Ctrl, jetpack 0x38 Alt (DOSBox-X mapper names up,
  pageup, right, pagedown, down, end, left, home, lctrl, lalt). Diagonal keys
  override the cardinal ones (`read_keyboard_input`). Jump = N/NE/NW while
  walking. Observed: `keys_down` 77/75/72/73/71 with the expected moves in
  level1_complete.txt.
- **Starting a game**: any key with a BIOS code (or fire) during the title
  (polled every 6 retraces) -> `init_game_state`, `load_level`,
  `redraw_screen`, then `wait_for_input` (polls every 20 retraces) until a
  direction is held or a key is in the BIOS buffer. Level transitions and
  restarts after a death end in the same `wait_for_input`.
- **Movement cadence** (oracle, level1_complete.txt): walking 2 px every 3rd
  tick; jump steps and horizontal jump moves every 2nd tick (the 46-entry
  `g_jump_dy`, apex 32 px, horizontal motion only while the key is held);
  falling 1 px down (+1 px sideways if held) every tick; reversing while
  walking adds a 2 px step (`g_prev_dir`). A tapped direction still acts
  (g_input_dir is kept until an acting tick consumes it).
- **Death sequence** (game_over_highscore.txt): deadly tile -> sound 3,
  state 0x60; the next tick erases Dave and spawns the explosion WITHOUT a
  `WaitVBL` (two ticks in one retrace); 300-tick death timer; `handle_death`
  removes a life and restarts at the level start (`wait_for_input`); lives
  -1 ends the game; `check_high_score` writes DSCORES.DAV (9-byte records:
  level, 5 score digits, 3 initials, upper-cased).
- **Default high-score file**: `assets/` has no DSCORES.DAV; the game
  writes its default (5 x level 1, 00100, "JON") at start-up
  (`init_game_once`); the oracle records and compares it.
- **Attract demo sequencing**: seed = low word of time() = 5968 + DOS
  seconds of day at 01/01/1991 (Borland's default EST offset); demo =
  rand() * 5 / 32767; next choice after the demo, the high scores (1000
  retraces) and the title (1200). From 00:00:00 the choices are 1,3,0,4,
  then 1,4,1,4,... (demo 2 never, 600 s observed); from 00:00:28 they are
  2,0,3,0,3,0,4,1 (attract_all_demos.txt). Demo lengths in ticks: 0: 2324,
  1: 1176, 2: 818, 3: 583, 4: 1300 (one tick per input byte; `0x20 n` =
  n + 1 idle ticks).
- **U-M1 item 4 observed** (attract_out_of_range_demo.txt, dos_time
  00:16:55, seed 7002): index 5, g_demo_pos 0x2002, level byte 2 (level 3),
  the CGA tileset bytes played as input; Dave dies at tick 600, and 300
  ticks later `handle_death`'s `wait_for_input` waits for LIVE input inside
  the demo: the attract mode freezes until a key is pressed. (A built-in
  demo always reaches its 0x30 within 300 ticks of a death.)

### Open

- **U-S3** The DOS time of day runs slow while sounds are requested: each
  accepted `PlaySound` (and `StopSound`/`PauseSound`) reprograms PIT
  channel 0 and resets `TickCount`, dropping the partial BIOS tick. Measured
  (seeds of attract_all_demos.txt): 39-62 DOS seconds per 40.6-66.1 s of
  emulated time between demo choices, overall 0.93-0.94. Model it exactly
  (per restart loss) so the native clock input reproduces the demo choices
  after the first one (state-model.md D7).
- **U-O1** Corpus gaps (FIDELITY.md section 5): live keyboard play beyond
  level 1 (jetpack, gun, climbing are only covered through demo input);
  warp zones (levels 5, 8, 9, 10) and the level -1 warp (U-M3; level 6's
  top row is open at columns 85-98, collision tests return 0 above the
  playfield, so Dave can pass x 0x132 at view 80 there); fire/jetpack on
  release (U-G9 b) with keys; control panel and F-key screens. Notes for
  whoever continues: replaying a demo's per-tick input live reproduces its
  path (demo 1's inputs from the tick after a straight-up jump at level 2's
  start -- the jump clears `g_prev_dir` = 6 left by level 1 -- reached the
  trophy and the column 16-20 ledge), but no demo reaches a door. On level
  2 the door (47,1) is reached through the shaft at column 32 (rows 1-3)
  from the maze around columns 23-36; stepping from the (23,3) brick onto
  the row-2 bricks at columns 24-28 leaves about 1 px of margin, because
  the row-0 ceiling stops the jump at y 31. Level 3 has a top-row opening
  at columns 72-74 (jetpack at (66,8)): the cheapest route to the level -1
  warp once level 2 is done (demo 0 collects that jetpack).
- **U-O2** A true 4-plane EGA image at every tick head needs an emulator
  command that reads DOSBox-X's `vga.mem.linear` (not in acceptance build
  v3); today: the read-map plane per tick plus 4-plane images inside
  `SaveUnderEGA` (oracle.py `ega_planes`).

## World lane (N3) additions (2026-10-20)

Appended by the native world worker (check_collisions, pick_up_items,
level_complete, check_warp_transition, attract_mode and their helpers in
`port/game/`). Evidence: the native code is byte-equal to the original on
the oracle runs named in docs/NATIVIZATION_LEDGER.md section D, or (marked
*code only*) read from src/DAVE.C.

### Closed (with evidence)

- **g_tiles before the first level load** is still all zero (BSS): the
  title tick's pre-state has a pristine level-1 record in g_levels but a
  zero g_tiles. A movmem(g_tiles, g_level, 1000) at that point would
  therefore clear the live map. Native: `level.pristine_loaded`
  (data:g_tiles); after a load g_tiles is exactly the resource map of
  `level.index` (rebuilt by the bridge, compared on every corpus tick).
- **load_level leaves stale animated-tile records**: it clears only the
  `active` word of the 200 records and writes `count = 0` into the record
  after the last new one; first/cur/col/row (and counts further on) keep the
  previous level's values. Observable state; reproduced (attract_mode and
  level_complete ticks equal on the whole g_anim_tiles).
- **load_level keeps the jetpack fuel and fuel tick** while dropping gun,
  jetpack and trophy (their icons are XOR-erased first).
- **Pickup order**: the four tiles under Dave are read first, then tested
  per pickup kind in table order (door, jetpack, gun, trophy, gems 47..52)
  and per kind in the order TL, TR, BL, BR; several items are collected in
  one tick. The 0-point gun and jetpack still run the score path
  (update_score, StopSound, PlaySound 6, tile cleared). The door scores 2000
  and sets `g_level_done` on every tick it is touched with the trophy.
- **Collision pass 1 does not stop at a hit** (*code only*): after
  `state &= 0xC0` the loop continues, so a second overlapping monster also
  dies and spawns a second type-5 explosion (re-arming the death timer).
- **redraw_screen can change game state** (*code only*): it calls
  draw_inventory -> update_score, so a pending extra life would be awarded
  there.
- **Warp-zone return** (*code only*): level_complete increments the level and
  draws its number, then a warp zone sets `g_current_level =
  g_warp_return_level`, the level the warp was ENTERED from; that level is
  loaded from its start, with its warp now marked used.
- **RowTimes100 overrun** (refines U-M1 item 2): the 10-entry row table is
  followed by TileRowOfs (n * 640, n = 1..10) and VgaTileRowOfs (n * 5120)
  and preceded by LevelOfs (n * 1280). So `tile_at` row 10 reads map offset
  640 + col (row 6, column 40 + col) and row 11 offset 1280 + col (the next
  record at the same column), not "past the map". Native `row_offset()`
  keeps these values (*code only*: no corpus tick reaches them).
- **Borland rand() in the port** (U-S1): `port/game/rng.c` on
  game.rng_seed, verified by every attract_mode tick that loads a level
  (rand_seed, every random tile phase and monster frame equal) and by the
  out-of-range demo: srand(7002) gives rand() = 32767 and index 5 natively
  too.

### Open

- **U-W1** The bridge's per-call input reconstruction
  (port/tests/bridge/world_io.c) places the poll after r retraces at
  tick-head time + r retrace periods and models the BIOS buffer as empty at
  the start of the call. Exact for the corpus (keys half-way between WaitVBL
  exits); a call entered with a key already buffered by an earlier tick, or
  typematic repeat, is not modelled. To be replaced by the per-retrace input
  of D2 (the oracle's `retraces` capture records `bios_keys`).
- **U-W2** The ending after level 10 (border chase, U-G8) and the warp
  sequences (real warp zones and the level -1 warp, U-M3/U-O1) have native
  code but no corpus tick; check_warp_transition is verified only as "no
  change" on non-warp ticks.
## Native player lane additions (N2, 2026-10-20)

Evidence: `port/game/player.c` equivalent to the original over the corpus
below (`tests/test_native.py` NativePlayerTest), and code reading.

- **U-G9 (b) observed** (tests/oracle/n2_buttons.txt): the fire and
  jump/jetpack buttons act when their signed-char counter reaches 0. A tap
  of a few ticks counts 30 -> 27, the release tick drops it to 0 and the
  action runs (counter back to 30) on that same tick; a hold triggers after
  30 held ticks and then every 30 (10 fire and 9 jetpack triggers on level 1,
  where neither has an effect besides the counters). Both buttons count
  independently when held together. (a) is still open: no multi-bit
  movement state occurs in any corpus tick, and the corpus has no live play
  on a level with ladders (levels 1, 5, 7, 8, 10 in 1-based numbering have
  them; level 1's room does not).
- **N2-1 RowTimes100 overrun.** `RowTimes100` (tiles.asm, DS 0x13DD) has 10
  entries and `TileRowOfs` follows it, so `tile_at`'s accepted rows 10 and 11
  use flat offsets 640 and 1280 (not 1000 and 1100): row 10 reads map row 6
  column 40 + col, row 11 reads past the map (the record's 24-byte tail, then
  the next record's path). `tile_attr_at_offset` (no checks) continues with
  1920.. for rows 12-19. Correction to U-M1 item 2 ("rows 10-11 past the
  map"). Unreached in the corpus (ladders end at row 8 in every level, so a
  climbing probe never asks for row 10); reproduced once, in
  `level_probe.c row_offset()`, used by tile_at, tile_attr_at (tiles.c) and
  tile_attr_at_offset (whose rows outside 0..9 were read as attribute 0
  before; no corpus tick reaches them). `g_tile_climbable[]` of such bytes
  reads the same constant window as g_tile_attr (`tile_climbable()`).
- **N2-2 Demo jump bit is signed.** process_input reads demo bytes through a
  signed `char far *`: `jump = byte >> 6` is -1 / -2 for a byte with the
  fire bit (0x80) set, so such a byte neither counts the jetpack button down
  nor releases it (`== 1` / `== 0` both fail). In the shipped demos every
  fire byte meets a jetpack counter at 30, so the quirk has no observable
  effect there (a mutant `(byte >> 6) & 1` is equivalent on the corpus).
- **N2-3 Movement-branch asymmetries** (reproduced): walking left does not
  record `g_prev_dir` at the end of the step (walking right does); a walk
  step that starts a fall still animates and moves 2 px; the fall's landing
  probe ORs the two attributes, so solid + deadly (3) does nothing (no move,
  no landing, no death) and the jetpack's sideways probe treats 3 as free;
  climbing down requests sound 4 twice.
- **N2-4 Retraces per tick** (U-T1, partial): in play and demo ticks without
  a level change, the original's retraces between tick heads equal exactly
  the WaitVBL calls of move_dave (1 per call, + up to 15 when scroll_screen
  scrolls, 0 on the killed tick and when no movement bit is set) plus
  handle_death's restart (1 + 20 per wait_for_input round). Evidence: the
  native counts equal `frames_since_prev` on every such tick of the corpus.
- **N2-5 The BIOS key buffer holds the last key.** The INT 9 handler empties
  the BIOS buffer on every make code before chaining to the BIOS, which then
  stores that key, so `bioskey(1)` sees the LAST key pressed until something
  reads it. During play the arrow keys stay in the buffer: handle_menu_key
  sees e.g. 0x4D, which is inert outside demos; wait_for_input's flush
  removes it. The input model carries it as `frame_input.menu_key`.
- **N2-6 A level record can keep an edit after a demo ends** (CLOSED
  2026-10-20 by state-model D8: all level maps are live state). When a demo's end byte (0x30) is read, process_input restores the
  live map from g_tiles, but the same tick's pick_up_items still runs and can
  remove a pickup from the record in g_levels; the next attract_mode loads
  another level, so the edit stays in that level's record for the rest of the
  program (n2_demos.txt: demo 4 ends at tick 10263 with level 5's tile at
  DS 0x2D8B taken; the native bridge, which treats non-current records as
  the pristine resource, diverges in its identity check at tick 10264). A
  later demo or game on that level would then start without that pickup.
  The native model needs per-record edits (or a "dirty record" overlay) in
  struct game to reproduce it.
- **U-M1 item 4, the garbage demo's stream** (n3_out_of_range_demo.txt):
  process_input plays the bytes after 0x2002, i.e. the CGA tileset segment
  that follows the demo bank in the load module (never modified at run
  time); the native resources carry them as `demo_overrun` and
  process_input matches the original on that run.

## Native integration (M3.3) additions (2026-10-20)

Free-running replay of the native `game_tick()` (port/game/game.c,
tools/native_replay.py) over n3_level1_complete, game_over_highscore,
inv_demos_all, n2_demos, n1_ega_demo2 and n1_cga_demo2 (fresh runs of this
date). Evidence for every item: those runs plus the replay's report.

### Closed (with evidence)

- **M3-1 The pipeline needs no state outside struct game.** Imported once at
  tick 1 and then driven by inputs alone, the native game equals the
  original on the whole game view after each of 21,643 passes (title -> game
  start, level 1, the level-complete corridor, level 2, four deaths, game
  over; all five demos with their high-score / title cycles and the
  time(NULL) demo choices; EGA and CGA). Values that cross subsystems within
  a pass (input_dir latched by process_input and consumed by move_dave, the
  killed bit set by check_collisions and acted on by move_dave next tick,
  the death timer armed by spawn_explosion, level.done, the map restore of a
  demo end followed by the same pass's pick_up_items, N2-6) were all already
  struct game fields. The composition added only the inner loop's exit
  (game_over) and the stop on a menu request.
- **M3-2 The input sample is the key table at the read, not at the tick
  head.** The oracle's dump points (tick head, boundary snapshots) are
  instants; a scripted key event is delivered to the INT 9 handler some
  0.5-1 ms after its scripted time, one scan code at a time, so it can land
  between a dump and the next read: in this date's n3_level1_complete run
  the PageUp release scripted at 15052 ms is not in g_keydown at the tick
  210 head (15052.60 ms) nor at the process_input boundary, but
  process_input read it (input_dir became 2, not 1; g_keydown at the
  move_dave boundary is [0x4D]). process_input never writes g_keydown, so
  the table after it is what it read. The free run therefore takes, for
  play/demo passes, g_keydown at the move_dave boundary when the run has
  boundary snapshots (1 of 943 n3_level1_complete passes differs from the
  head table), else at the tick head. The same delivery made
  `tools/native_check.py process_input` fail on that run at tick 210
  (the bridge used the pre-call table): an input-reconstruction limit of
  the bridge (U-W1), not a native behaviour difference; fixed the same way
  (native_check passes the post-call g_keydown as the `keys` of each
  process_input pair, world_io.c uses it). The main
  checkout's earlier run of the scenario has the tick 210 head at
  15056.78 ms, 4.8 ms after the event (the per-run phase, FIDELITY.md 1),
  and passes; in this run the 15052 ms event sits 0.6 ms before a sampling
  edge (`--snap` would move it).
- **M3-3 (closes U-T3's +-1) A title pass that times out is always 1200 + 1
  WaitVBL calls; frames_since_prev is elapsed time.** frames_since_prev =
  round(elapsed / nominal period) between two tick heads, while the game
  counts WaitVBL calls (edge-triggered: wait for the end of the current
  retrace, then for the next start). Per-retrace captures count the calls
  exactly: 1201 WaitVBL exits in the title pass of a CGA run of
  n1_cga_demo2.txt with `retraces 2000` added (scratch run; elapsed
  20056.0 ms = 1201.8 CGA periods -> "1202") and 1201 natively (603 = 603
  in game_over_highscore, whose title Space ends); inv_demos_all's VGA
  title pass (native 1201) measures
  "1200" because the head lies just before a retrace edge after the mode
  set and redraw. Not an INT 8 effect.

### Open

- **U-P1 Elapsed retraces exceed WaitVBL calls when a frame's work
  overruns the retrace period.** n1_cga_demo2 tick 521 (scroll by 15
  columns): native and original both call WaitVBL 16 times (a per-retrace
  capture of the same scenario shows 16 exits, the 15 scroll steps 2.00
  CGA periods apart), but each step's full-view CGA redraw (DrawLevelView +
  draw_actors) takes longer than one 16.69 ms frame on the oracle's emulated
  386 (cycles fixed 20000), so each wait catches the NEXT retrace: 31
  retraces elapse. Not in VGA or EGA (all scroll passes 16). It is a
  property of the original's CPU cost on that machine, not of the game
  logic: a native frame is one WaitVBL (D2). Reproducing the elapsed time
  needs a per-draw cost model in present/ (or declaring elapsed-time
  equivalence in CGA outside the contract); decide with D2's timing design.
- **U-P2 Menus and the demo end by a key inside a pass.** handle_menu_key
  runs its popups (F1/F2/F3/F9/F10/Esc) and the demo exit (restore map,
  play mode, StopSound, init_game_state, load_level, redraw_screen,
  wait_for_input) INSIDE process_input, before move_dave of the same pass.
  game_tick stops the pass after process_input and returns the request
  (TICK_MENU); no corpus pass reaches it. Needs the D2 resumable sequence
  and a scenario that presses a key during a demo / a menu key in play.
- **Oracle feature requests (for the owner of tools/oracle.py):** (a) a
  per-tick capture of g_keydown (256 bytes) at process_input's
  get_player_input call (or right after process_input), so runs without
  boundary snapshots give the exact input sample of M3-2; (b) `retraces`
  captures in the EGA/CGA scenarios, so WaitVBL counts (not only elapsed
  retraces) are compared there; (c) the tick head's BIOS key buffer (as
  `retraces` records it) on every tick, for the persistent one-key buffer
  the free run models from the key events (N2-5).
