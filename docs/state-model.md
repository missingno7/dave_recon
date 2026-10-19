# Native game-state model (proposal, PORT_ROADMAP M2.3)

**Status: proposal for supervisor approval.** Nothing here is code yet; no
`port/` file is created or changed by this document. It designs the single
native `struct game` (PORT_ROADMAP decision 4) from the semantic inventory.

Every mapping cites its inventory entry (`data:<name>`, `c:<function>`,
`asm:<procedure>`, `format:<record>`) in `docs/semantic-inventory.json` /
`.md`, where the address, size, type, mechanical readers/writers (per struct
field) and evidence live. Closed ledger items it relies on: U-G1..U-G8,
U-S1, U-S2, U-M1, U-M2 (`docs/UNDERSTANDING_LEDGER.md`).

## 1. Principles

1. **Membership comes from the inventory role.** `game_state` objects become
   fields of `struct game`; `game_constant` objects become `const` tables in
   `port/game`; `presentation_state` / `presentation_constant` go to
   `port/present`; `platform_state` to `port/platform` (most of it disappears);
   `config` to a `struct settings` passed in, not owned by the game;
   `resource_buffer` to immutable resource objects built by the codecs;
   `layout_artifact` is eliminated (the bridge regenerates its bytes).
2. **Widths are the original's** where a value is observable (in a DGROUP
   snapshot, in a comparison, or through wrap-around): `int16_t` for `int`,
   `uint16_t` for `unsigned`, `int8_t` for `char`/`signed char`, `uint32_t`
   for `unsigned long`. The arithmetic quirks are written out at the sites
   that have them (section 6), not hidden in the types.
3. **Array of structs, view-relative coordinates kept.** The original's
   struct-of-arrays (`data:g_monsters`) becomes an array of structs; x stays
   in view pixels (`level_x = x + 16 * scroll_x`) because scrolling, shots,
   collisions and the bridge all use it.
4. **Mode-independent state.** Per-video-mode sprite ids chosen by game logic
   (`data:g_dave_sprite`, `data:g_dave_mask`, `g_monsters.sprite`) are
   replaced by mode-independent poses/frames; the presentation layer (and the
   bridge) maps them to ids with the per-mode tables.
5. **The existing native piece is adopted unchanged:** `port/game/anim.h`
   `struct anim_state` (`data:g_anim_tiles`, `data:g_anim_tick_divider`) is
   `game.anim`.

## 2. `struct game` (sketch)

```c
/* port/game/state.h -- PROPOSAL. Comments: inventory id; original DS for the bridge. */
#include <stdint.h>
#include "anim.h"                       /* struct anim_state (existing) */

enum game_mode { MODE_PLAY = 0, MODE_DEMO = 1, MODE_SCORES = 2, MODE_TITLE = 3 };

/* data:g_dave_state bits (U-G1) */
enum { DAVE_JETPACK = 0x01, DAVE_CLIMB = 0x02, DAVE_WALK = 0x04, DAVE_FALL = 0x08,
       DAVE_JUMP = 0x10, DAVE_ALIVE = 0x20, DAVE_KILLED = 0x40 };

/* what Dave looks like; mapped to per-mode sprite ids by the presentation */
enum dave_pose { POSE_FRONT, POSE_WALK_LEFT, POSE_WALK_RIGHT, POSE_JUMP_LEFT, POSE_JUMP_RIGHT,
                 POSE_CLIMB, POSE_JET_LEFT, POSE_JET_RIGHT };

struct player {                 /* Dave */
    int16_t  x, y;              /* data:g_player_x (56EA), data:g_player_y (56EC); view px */
    uint16_t state;             /* data:g_dave_state (6156); DAVE_* bits, low byte used */
    int16_t  facing;            /* data:g_dave_facing (5740): 0 left, 1 right */
    int16_t  jet_facing;        /* data:g_jet_facing (57E6) */
    int16_t  jump_pos;          /* data:g_jump_pos (579A): index into jump_dy */
    int16_t  move_throttle;     /* data:g_death_pause (5794) -- renamed (U-G2) */
    int16_t  input_dir;         /* data:g_input_dir (57E2): 0..7, 8 = none */
    int16_t  prev_dir;          /* data:g_prev_dir (579E) */
    int16_t  anim_frame;        /* data:g_anim_frame (6150): 0..3 */
    int16_t  anim_delay;        /* data:g_anim_delay (6548) */
    int16_t  death_timer;       /* data:g_bonus_timer (6546) -- renamed */
    uint8_t  pose, pose_frame;  /* replaces data:g_dave_sprite (573E) + data:g_dave_mask (57E4) */
};

struct inventory {
    int16_t has_gun;            /* data:g_has_gun (4F84) */
    int16_t has_jetpack;        /* data:g_has_jetpack (4F8A) */
    int16_t got_trophy;         /* data:g_got_trophy (4F88) */
    int16_t jetpack_fuel;       /* data:g_jetpack_fuel (5798): 60 .. 0 */
    int16_t fuel_tick;          /* data:g_fuel_tick (6154): 15 .. 1 */
};

struct monster {                /* data:g_monsters (5742), format:monster_block */
    int16_t  active, x, y;      /* x in view px */
    uint16_t path_pos;          /* unsigned byte index into the level's path */
    int16_t  reload, fire_count, move_count, anim_count, anim_frame;
    int16_t  shown_frame;       /* replaces .sprite: the frame last drawn (section 5) */
};

struct shot {                   /* data:g_shots (56F6), format:shot_record */
    int16_t active, x, y, dir, frame, kind, owner;   /* owner = .id: monster i+1, Dave 5 */
};

struct explosion {              /* data:g_actors (4F8E), format:actor_record (first 14 bytes) */
    int16_t active, x, y, frame, life, anim, type;   /* type: written, never read */
};

struct level_state {
    int16_t index;              /* data:g_current_level (56F4); 0-based, -1 reachable (U-M3) */
    int8_t  map[10][100];       /* the live map: data:g_levels[index] tiles as edited (pickups) */
    int16_t scroll_x;           /* data:g_scroll_x (57A0): 0..80 */
    int16_t done;               /* data:g_level_done (6158) */
    int16_t in_warp_zone;       /* data:g_in_warp_zone (573C) */
    int16_t warp_return;        /* data:g_warp_return_level (6152) */
    int16_t warp_used[10];      /* data:g_level_visited (57AA) */
};

struct buttons {                /* process_input's edge detection (U-G9) */
    int8_t fire_repeat;         /* data:g_fire_repeat (00AC): 30 idle .. 0 = trigger */
    int8_t jetpack_repeat;      /* data:g_jetpack_repeat (00AD) */
};

struct demo_playback {          /* format:demo_stream; the bank itself is a resource */
    int16_t pos;                /* data:g_demo_pos (57A2) */
    int8_t  idle_run;           /* data:g_demo_repeat (6544): wraps as 8-bit */
};

struct score_entry {            /* data:g_hiscores (57BE), format:hiscore_entry */
    int16_t  level;             /* 1-based; 11 = won */
    uint16_t score16;           /* truncated, as the original compares it (U-M1 item 7) */
    char     initials[3];
};

struct game {
    int16_t          mode;          /* data:g_demo_mode (00AA) -- renamed: enum game_mode */
    int16_t          game_over;     /* data:g_game_over (5792) */
    uint32_t         rng_seed;      /* data:rand_seed (4BB6): Borland LCG state (U-S1) */
    uint32_t         score;         /* data:g_score (4C60): capped at 99999 */
    uint32_t         next_extra_life; /* data:g_next_extra_life (6148) */
    int16_t          lives;         /* data:g_lives (56EE): -1 = game over */
    struct player    dave;
    struct inventory inv;
    struct level_state level;
    struct anim_state anim;         /* data:g_anim_tiles (57E8), data:g_anim_tick_divider (615A) */
    struct monster   monsters[4];
    struct shot      shots[5];
    int16_t          shot_anim_count; /* data:g_shot_anim_count (5796): shared by all shots */
    struct explosion explosions[6];
    struct buttons   buttons;
    struct demo_playback demo;
    struct score_entry scores[5];   /* in-memory table; the DSCORES.DAV image is a file record */
    struct sequence  seq;           /* NEW: in-tick multi-retrace sequences (section 7, Q2) */
};
```

`struct sequence` is a placeholder for the state that the original keeps on
the stack during multi-retrace sequences (section 7, question Q2).

## 3. Mapping of every `game_state` object

| original | native | width | note |
|---|---|---|---|
| `data:g_demo_mode` | `game.mode` | int16, 0..3 | the name is historical: it is the game mode (title/scores/demo/play); `data:g_demo_state` (DS 0x9EC2) is a dead recorder flag (N-1) |
| `data:g_game_over` | `game.game_over` | int16 | also set to leave a won game and by F3 restart (via mode 3) |
| `data:g_quit` | (none) | -- | constant 0 after init; the bridge writes 0 |
| `data:rand_seed` | `game.rng_seed` | uint32 | Seed*0x015A4E35+1, output (Seed>>16)&0x7FFF; `srand(time)` takes the low 16 bits of an injected time |
| `data:g_score` | `game.score` | uint32 | unsigned long compares in `c:update_score` |
| `data:g_next_extra_life` | `game.next_extra_life` | uint32 | multiple of 20000 |
| `data:g_lives` | `game.lives` | int16 | -1 is the game-over value |
| `data:g_player_x` / `data:g_player_y` | `dave.x` / `dave.y` | int16 | y: `& 0xFF` after every jump/fall step (U-G2) |
| `data:g_dave_state` | `dave.state` | int16 storage, bit set | U-G1; multi-bit states allowed (U-G9) |
| `data:g_dave_facing`, `data:g_jet_facing` | `dave.facing`, `dave.jet_facing` | int16 | |
| `data:g_jump_pos` | `dave.jump_pos` | int16 | |
| `data:g_death_pause` | `dave.move_throttle` | int16 | renamed: movement throttle (U-G2) |
| `data:g_input_dir`, `data:g_prev_dir` | `dave.input_dir`, `dave.prev_dir` | int16 | the input latch belongs to Dave's movement (consumed = 8) |
| `data:g_anim_frame`, `data:g_anim_delay` | `dave.anim_frame`, `dave.anim_delay` | int16 | U-G4 |
| `data:g_bonus_timer` | `dave.death_timer` | int16 | renamed; wraps through -1 (level -1 only) |
| `data:g_has_gun`, `data:g_has_jetpack`, `data:g_got_trophy` | `inv.*` | int16 | dropped by `c:load_level`, kept across deaths |
| `data:g_jetpack_fuel`, `data:g_fuel_tick` | `inv.jetpack_fuel`, `inv.fuel_tick` | int16 | |
| `data:g_current_level` | `level.index` | int16 | signed: -1 reachable |
| `data:g_levels` (current record's map) + `data:g_level` | `level.map` | int8[10][100] | the original edits `g_levels` in place through `g_level`; native keeps a copy loaded from the resource |
| `data:g_tiles` | (none: derivable) | -- | pristine copy = resource map of `level.index` (except level -1, U-M3) |
| `data:g_scroll_x` | `level.scroll_x` | int16 | |
| `data:g_level_done`, `data:g_in_warp_zone`, `data:g_warp_return_level`, `data:g_level_visited` | `level.*` | int16 | |
| `data:g_anim_tiles`, `data:g_anim_tick_divider` | `game.anim` | struct anim_state | existing `port/game/anim.h` |
| `data:g_monsters` | `game.monsters[4]` | int16 / uint16 path_pos | struct-of-arrays -> array of structs; `.sprite` -> `shown_frame` |
| `data:g_shots` | `game.shots[5]` | int16 x 7 | `id` renamed `owner` |
| `data:g_shot_anim_count` | `game.shot_anim_count` | int16 | decremented once per active shot (quirk) |
| `data:g_actors` | `game.explosions[6]` | int16 x 7 | the 300-byte tail is dropped; the bridge writes zeros |
| `data:g_fire_repeat`, `data:g_jetpack_repeat` | `game.buttons.*` | int8 | release-triggered (U-G9) |
| `data:g_demo_pos`, `data:g_demo_repeat` | `game.demo.*` | int16, int8 | |
| `data:g_hiscores` | `game.scores[5]` | int16 / uint16 / char[3] | |
| `data:g_dave_sprite`, `data:g_dave_mask` | `dave.pose`, `dave.pose_frame` | uint8 | presentation hint chosen by game logic (section 5) |

## 4. Not game state

**Constants (`game_constant`, `port/game` const tables):** `data:g_jump_dy`,
`data:g_level_flags`, `data:g_level_start_x`, `data:g_level_start_y`,
`data:g_monster_width`, `data:g_monster_height`,
`data:g_warp_target_level_plus1` (store it 1-based to keep the "0 - 1 = -1"
semantics explicit), `data:g_warp_start_scroll_x`, `data:g_warp_start_x`,
`data:g_pickup_tile_ids`, `data:g_pickup_points`, `data:g_tile_climbable`,
`data:g_tile_attr`, `data:g_animated_tile_ids`, `data:g_animated_tile_frames`,
`data:g_level_monster_init`, `data:init_game_once_default_scores_image`.
The level records (`format:level_record`: map + monster path) and the demo
bank (`format:demo_stream`) are immutable resources read by the game.

**Presentation (`port/present`):** the framebuffer itself (XOR sprites make
it stateful, see Q1); `data:g_gfx_index` and the per-mode sprite/tile tables
(`data:g_sprite_sets`, `data:g_spr_*`, `data:g_mask_*`, `data:g_status_tiles`,
`data:g_status_row_len`, `data:g_tile_digit0`, `data:g_title_anim_tiles`,
`data:g_warp_tube_tile`, `data:redraw_screen_logo_image`,
`data:level_complete_msg_image`, the string pools); text state
(`data:g_text_x`, `data:g_text_y`, `data:g_text_left`, `data:g_win_x1`..`y2`,
`data:XorMask`); the save-under buffer `data:g_dave_background`
(`format:save_under_buffer`); control-panel cursor/choices (`data:g_panel_*`,
`data:g_cur_*`, `data:g_saved_*`); picfile tables (`data:g_pic_table`,
`data:g_pic_charptr`, `data:g_pic_picptr`, `data:g_pic_planes`);
`data:g_vga_palette`, `data:BarPattern`.

**Settings (`struct settings`, owned by the platform/front end, passed in):**
`data:g_video_mode`, `data:SoundEnabled`, `data:g_input_device` (only
player 1 is ever read), `data:g_key_scans`, `data:g_joy_xmin`..`ymax`,
`data:g_mouse_deadzone`.

**Platform (`port/platform`, mostly gone):** `data:g_keydown` (the input
table the platform fills), `data:g_old_int9`, `data:OldInt8`,
`data:TimerHooked`, the sound driver's variables (`data:TickDivide` ..
`data:SavedRate`, `data:SoundPtr`, `data:SoundPriority`: the native sound
scheduler owns the equivalent), `data:g_adapter_type`, `data:g_have_*`,
`data:g_alloc_block`, the RLE variables, VideoID's CS data, the blitters'
CS scratch words.

**Eliminated layout artifacts (bridge regenerates the bytes):** the six
`g_unused_*` holes (U-M2) and the paddings; `data:g_actors` tails;
`data:g_level`, `data:g_level_path`, `data:LevelPtr` (pointers: derived from
`level.index`); `data:RowTimes100`, `data:LevelOfs`, `data:TileRowOfs`,
`data:VgaTileRowOfs` and the six `*RowOfs` tables (multiplication tables);
`data:g_quit` (constant 0); the dead features' state (`data:g_demo_recording`,
`data:g_demo_state`, `data:g_demo_ptr`, `data:g_demo_buffer`, the asm RNG
`data:RndTable`/`RndIndex*`/`RndInit`); never-read copies
(`data:g_pic_sprites`, `data:g_pic_spriteptr`, `data:g_pic_tileptr`,
`data:TileErrMsg`, `data:tiles_anon_*`).

## 5. What the bridge must reconstruct (export native -> DGROUP)

| DGROUP bytes | from |
|---|---|
| `g_dave_sprite` / `g_dave_mask` | `pose`, `pose_frame`, gfx mode, via the per-mode tables (front, sets 9/10, 11/12, 3/4, 5/6, 7/8, jump left/right) |
| `g_monsters.sprite[i]` | `shown_frame`, `level.index`, gfx mode: `(level-2)*8+0x7D+2f` (CGA), `(level-2)*16+0xC5+4f` (EGA), `(level-2)*4+0x59+f` (VGA). `shown_frame` is needed because the original computes the sprite BEFORE advancing `anim_frame`, and `c:redraw_screen` resets it to frame 0 |
| the current record of `g_levels` | `level.map` (other records: the resource) |
| `g_tiles` | the resource map of `level.index` |
| `g_level`, `g_level_path`, `LevelPtr` | `0x173A + 0x500*index (+0x100)`, `DGROUP:0x173A` |
| actor tails, holes, pads, `g_quit`, dead-feature state | zeros / constants (verified constant over the corpus: `actor bytes 14..0x139 never change`) |
| `g_hiscores` | `scores[]` (the 45-byte DSCORES image lives in the near heap at DS 0xA1BE, outside the oracle's dump) |

## 6. Observable widths and arithmetic (to reproduce explicitly)

- `dave.y`: jump/fall steps are `y = (y + t) & 0xFF` (`c:move_dave`), so
  jumping through the top wraps to 240..255 (observed); elsewhere y is a plain
  int16 (`c:check_warp_transition`'s tube, `c:level_complete`).
- Pixel -> tile column: C division truncates toward zero (also in C11): a
  probe at x = -2 maps to column `scroll_x`, not `scroll_x - 1`; columns are
  not range-checked (column 100 = next row; U-M1 item 2) -- keep the
  original's flat `row * 100 + col` indexing of a 1000-byte map **plus the
  bytes that follow it** if the out-of-range reads are to be reproduced (Q4).
- Collision boxes in `c:check_collisions` use unsigned 16-bit differences,
  e.g. Dave vs monster: `a = (uint16_t)(m.x - dave.x); hit_x = a < 13 ||
  width > (uint16_t)-a` (`width` an int16 promoted to unsigned), likewise
  for y with 16 / height and for the two shot passes.
- Monster path bytes are signed (`int8_t`), the path index unsigned 16-bit.
- Score: `uint32`; the extra-life test is `score - next >= 20000` in unsigned
  32-bit; the cap 99999 is applied after the test.
- High scores: comparisons against the truncated 16-bit stored score (U-M1
  item 7); `c:init_game_once` decodes digits with int16 arithmetic.
- `rand()`: `(int32_t)rand() * n / 32767` in 32-bit (can equal n for
  rand() == 32767: demo choice, U-M1 item 4).
- 8-bit counters: `buttons.*` (signed char), `demo.idle_run` (char, an idle
  count >= 128 wraps through negative values and still takes n ticks).
- `dave.death_timer` decrements through -1 when not armed (level -1).

## 7. Open questions that block finalising the model

- **Q1 (rendering contract).** Monsters, shots, explosions and status icons
  are XOR-drawn and erased by redrawing (`c:xor_sprite`), Dave by
  save/restore-under: the framebuffer is state that cannot be recomputed
  from `struct game`. Does the native presentation keep a persistent
  framebuffer driven by draw events emitted by the game in the original
  order (like `anim_step`'s redraw callback), or redraw from state and accept
  pixel differences where XOR sprites overlap? Framebuffer equivalence
  (FIDELITY.md section 3) needs the former. Depends on U-R1.
- **Q2 (sub-tick sequences and input).** Several subsystems run many
  retraces inside one pipeline tick and read input or change game state on
  the way: `c:wait_for_input` (animates tiles 20 times per blink until
  input -- `game.anim` after the tick depends on WHEN the key came),
  `c:scroll_screen` (15 retraces), `c:check_warp_transition` (tube
  sequence), `c:level_complete` (432-retrace corridor walk, the ending),
  `c:check_high_score` (a mini game loop of up to 1000 retraces moving
  monsters/shots), `c:attract_mode` (title 1200 / scores 1000 retraces),
  `c:handle_death` (respawn + wait), the menus (`c:wait_key_cursor`, BIOS
  key reads). The original keeps their progress on the stack. Proposal:
  `game_step()` advances one RETRACE (frame) with a per-frame input sample
  (key-state table + at most one buffered key, as the INT 9 handler leaves
  the BIOS buffer), `struct sequence` holds the active sequence's counters,
  and a "tick" is the run of frames between two pipeline heads. Needs
  approval because it changes the `game_tick(struct game*, const struct
  tick_input*)` signature in PORT_ROADMAP decision 5, and the oracle corpus
  must then record input per retrace (M1.3).
- **Q3 (sprite representation).** Approve `pose`/`pose_frame` and
  `shown_frame` instead of storing per-mode ids (section 5), or keep the ids
  and the mode in game state.
- **Q4 (layout-dependent behaviour in the port).** The bad warp to level -1
  (U-M3) makes the collision map out of DGROUP bytes that include the BIOS
  INT 8 vector and the asynchronous sound-driver phase, and its monsters walk
  memory beyond the path. Options: (a) declare it outside the equivalence
  contract and implement a documented, deterministic stand-in; (b) reproduce
  it by modelling those bytes (an emulated memory image the roadmap
  forbids). Proposal: (a), after U-M3 has observed the original. The other
  out-of-range reads (U-M1 items 2, 4) are deterministic and can be kept by
  giving the map its trailing bytes and the demo reader the bank's
  neighbouring segment, or also declared out of contract (no corpus tick
  reaches them).
- **Q5 (naming in the oracle).** `tools/oracle.py FIELDS` calls DS 0x00AA
  `game_state` (correct) and DS 0x9EC2 `demo_mode` (the dead recorder flag,
  always 0, N-1). The native names above (`mode`, `move_throttle`,
  `death_timer`) differ from DAVE.C's historical names; the inventory keeps
  the historical ones as ids. Rename in `FIELDS` and the ledgers once
  approved (owner of `tools/oracle.py`).
- **Q6 (settings ownership).** `process_input`/`get_player_input` read the
  device choice and key bindings every tick and the control panel edits
  them mid-game (F2). Keep `struct settings` outside `struct game` and pass a
  pointer to `game_step()`, or copy into the game? Proposal: outside; the
  game only sees a logical input sample.
- **Q7 (RNG seed injection).** `game.rng_seed` must be exported for snapshot
  equality; the time-based `srand(time(NULL))` at the title timeout needs the
  emulated DOS time (pinned 1991-01-01 00:00:00 plus elapsed) as an input.
  Approve "time is part of the frame input".
