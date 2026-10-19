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
