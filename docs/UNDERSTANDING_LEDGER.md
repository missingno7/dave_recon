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
  the game's INT 8 rate) and its exact length.

### Gameplay (G)
- **U-G1** Dave state word (DS 0x6156): full bit semantics and transitions.
  Partial: 0x01 jetpack, 0x02 climb, 0x04 walk, 0x08 fall, 0x10 jump, 0x20
  alive, 0x40 killed.
- **U-G2** Jump trajectory table (DS 0x00BA, y deltas, 0x80 terminated) vs
  observed jump heights; speed throttle DS 0x5794.
- **U-G3** DS 0x0118 "per-level option byte" (102 refs together with
  0x6156): meaning.
- **U-G4** DS 0x6150 (animation frame?). (0x615A closed, see below.)
- **U-G5** Monster record fields (DS 0x5742-0x578A, 4 slots: active, x, y,
  path index, fire reload, sprite, anim count, frame, fire count, move count)
  and per-level monster init block (DS 0x0496, 10 x 0x50).
- **U-G6** Object/actor tables: DS 0x4F8E six 0x13A-byte actors and DS 0x56F6
  five 14-byte shots: full field list.
- **U-G7** `spawn_explosion` / `update_explosions` names are tentative.
- **U-G8** Off-by-one in `level_complete` (border path entry 47
  overwritten): observable effect?

### Rendering (R)
- **U-R1** Exact draw order per tick, and which routines draw to the visible
  page vs back buffers (save/restore-under semantics).
- **U-R2** EGA tile cache at A800h (latched copies): purpose and exact
  effect, so it can be expressed as a plain blit.
- **U-R3** CGA sprite "unread tails" (2,713 bytes) and sprite header misreads
  caused by the duplicated VGA-tileset byte at offset 0xFF00 (resources
  147-157): visible on screen?
- **U-R4** XOR font mask (DS 0x1392) usage and the cursor/text effects.

### Sound (S)
- **U-S1** RNG: which behaviours use Borland `rand()` (seeded by `time()`)
  and which use the asm lagged-Fibonacci generator; seed paths.
- **U-S2** Sound driver timing: per-sound tick multiplier -> PIT rate, the
  BIOS-chain divider, priority rules, behaviour on pause.

### Memory/layout (M)
- **U-M1** Any behaviour that depends on memory layout (out-of-bounds
  reads/writes, overlapping buffers, the level-6 warp reading DS 0x123A
  "level -1"): enumerate and determine the observable effect of each.
- **U-M2** 6 unreferenced BSS holes (`g_unused_*`): confirm unused.

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
