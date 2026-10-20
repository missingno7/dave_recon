/*
 * The complete gameplay state of Dangerous Dave: one struct, owned by the
 * game layer (docs/state-model.md, approved with decisions D1-D7).
 *
 * Only gameplay state lives here. Presentation state (framebuffer, per-mode
 * sprite/tile ids, text cursor), settings (video mode, input device, key
 * bindings, sound on/off) and platform state (keyboard table, timers) live
 * in their own layers. Integer widths are the original's wherever a value is
 * observable (docs/state-model.md section 6); the arithmetic quirks are
 * written out where they occur, not hidden in the types.
 *
 * Field comments give the original global (docs/semantic-inventory.json id)
 * for traceability; only the test-only bridge (port/tests/bridge) maps them
 * to original addresses.
 */
#ifndef DAVE_STATE_H
#define DAVE_STATE_H

#include <stdint.h>
#include "anim.h"

enum game_mode { MODE_PLAY = 0, MODE_DEMO = 1, MODE_SCORES = 2, MODE_TITLE = 3 };

/* Dave's state bits (U-G1). Several may be set at once (U-G9). */
enum {
    DAVE_JETPACK = 0x01, DAVE_CLIMB = 0x02, DAVE_WALK = 0x04, DAVE_FALL = 0x08,
    DAVE_JUMP = 0x10, DAVE_ALIVE = 0x20, DAVE_KILLED = 0x40
};

#define LEVEL_COUNT 10
#define LEVEL_ROWS 10
#define LEVEL_COLS 100
#define MONSTER_COUNT 4
#define SHOT_COUNT 5
#define EXPLOSION_COUNT 6
#define SCORE_ENTRIES 5

struct player {
    int16_t  x, y;           /* g_player_x, g_player_y: view pixels; y wraps as 8 bits in jumps (U-G2) */
    uint16_t state;          /* g_dave_state: DAVE_* bits */
    int16_t  facing;         /* g_dave_facing: 0 left, 1 right */
    int16_t  jet_facing;     /* g_jet_facing */
    int16_t  jump_pos;       /* g_jump_pos: index into the jump table */
    int16_t  move_throttle;  /* g_death_pause (misnamed historically): movement every 3rd/2nd/1st tick */
    int16_t  input_dir;      /* g_input_dir: latched direction 0..7, 8 = none */
    int16_t  prev_dir;       /* g_prev_dir */
    int16_t  anim_frame;     /* g_anim_frame: 0..3 */
    int16_t  anim_delay;     /* g_anim_delay */
    int16_t  death_timer;    /* g_bonus_timer (misnamed historically) */
    /* Pose/frame replacing the per-mode sprite ids g_dave_sprite (DS 0x573E)
     * and g_dave_mask (DS 0x57E4) (D3): what Dave looks like, chosen by the
     * game logic; present/ (and the bridge) map it to the per-mode ids. */
    uint8_t  pose;           /* enum dave_pose (data:g_dave_sprite + data:g_dave_mask) */
    uint8_t  pose_frame;     /* frame 0..3 within an animated pose (0 for still poses) */
};

struct inventory {
    int16_t has_gun;         /* g_has_gun */
    int16_t has_jetpack;     /* g_has_jetpack */
    int16_t got_trophy;      /* g_got_trophy */
    int16_t jetpack_fuel;    /* g_jetpack_fuel: 60 .. 0 */
    int16_t fuel_tick;       /* g_fuel_tick: 15 .. 1 */
};

struct monster {             /* g_monsters (struct of arrays in the original) */
    int16_t  active, x, y;   /* x in view pixels */
    uint16_t path_pos;       /* byte index into the level's monster path */
    int16_t  reload, anim_count, anim_frame, fire_count, move_count;
    int16_t  shown_frame;    /* g_monsters.sprite as a mode-independent frame (D3, state-model
                                section 5): the anim_frame the monster was last drawn with,
                                which move_monsters erases next; MONSTER_FRAME_UNKNOWN when an
                                imported sprite id decodes to no frame */
};
#define MONSTER_FRAME_UNKNOWN (-1)

struct shot {                /* g_shots */
    int16_t active, x, y, dir, frame, kind;
    int16_t owner;           /* .id: monster i+1, or 5 = Dave */
};

struct explosion {           /* g_actors (first 14 bytes; the 300-byte tail is never used) */
    int16_t active, x, y, frame, life, anim;
    int16_t type;            /* written, never read */
};

struct level_state {
    int16_t index;           /* g_current_level: 0-based; -1 is reachable (U-M3) */
    int8_t  backup[LEVEL_ROWS][LEVEL_COLS];  /* g_tiles: copy of the current level's live
                                map taken by load_level; restore_level_map copies it back */
    int16_t scroll_x;        /* g_scroll_x: first visible column, 0..80 */
    int16_t done;            /* g_level_done */
    int16_t in_warp_zone;    /* g_in_warp_zone */
    int16_t warp_return;     /* g_warp_return_level */
    int16_t warp_used[LEVEL_COUNT];       /* g_level_visited */
    int16_t pristine_loaded; /* 1 once a level was loaded (backup valid); 0 before the first
                                load_level, when the original's g_tiles is still all zero */
};

struct buttons {             /* process_input's release-triggered buttons (U-G9) */
    int8_t fire_repeat;      /* g_fire_repeat */
    int8_t jetpack_repeat;   /* g_jetpack_repeat */
};

struct demo_playback {
    int16_t pos;             /* g_demo_pos */
    int8_t  idle_run;        /* g_demo_repeat: 8-bit, wraps */
};

struct score_entry {         /* g_hiscores */
    int16_t  level;          /* 1-based; 11 = game won */
    uint16_t score16;        /* the original stores and compares 16 bits (U-M1 item 7) */
    char     initials[3];
};

struct game {
    int16_t  mode;           /* g_demo_mode (misnamed historically): enum game_mode */
    int16_t  game_over;      /* g_game_over */
    uint32_t rng_seed;       /* Borland rand() state (U-S1) */
    uint32_t score;          /* g_score: capped at 99999 */
    uint32_t next_extra_life;/* g_next_extra_life */
    int16_t  lives;          /* g_lives: -1 = game over */
    struct player dave;
    struct inventory inv;
    struct level_state level;
    /* D8: the live maps of ALL levels for the whole program run (the
     * original's g_levels records, edited in place). They start as the
     * resource maps; pickups edit the current one; restore_level_map undoes
     * edits from level.backup. An edit made after a restore persists into
     * later visits of that level (N2-6), exactly as in the original. */
    int8_t level_maps[LEVEL_COUNT][LEVEL_ROWS][LEVEL_COLS];
    int8_t stray_map[LEVEL_ROWS][LEVEL_COLS];   /* live map of level -1 (D4 stand-in) */
    struct anim_state anim;  /* g_anim_tiles, g_anim_tick_divider */
    struct monster monsters[MONSTER_COUNT];
    struct shot shots[SHOT_COUNT];
    int16_t shot_anim_count; /* g_shot_anim_count: shared by all shots */
    struct explosion explosions[EXPLOSION_COUNT];
    struct buttons buttons;
    struct demo_playback demo;
    struct score_entry scores[SCORE_ENTRIES];
    /* struct sequence (D2: resumable multi-retrace sequences) is added with
     * the retrace-level step function. */
};


/* The live map of the current level (D8). */
static inline int8_t (*level_live_map(struct game *g))[LEVEL_COLS]
{
    return g->level.index >= 0 && g->level.index < LEVEL_COUNT
        ? g->level_maps[g->level.index] : g->stray_map;
}
static inline const int8_t (*level_live_map_c(const struct game *g))[LEVEL_COLS]
{
    return g->level.index >= 0 && g->level.index < LEVEL_COUNT
        ? g->level_maps[g->level.index] : g->stray_map;
}

/* What Dave looks like (struct player.pose), named after the original's
 * per-mode sprite/mask tables (src/DAVE.C). Animated poses index a frame
 * 0..3 of g_sprite_sets[set][mode][frame] (frames 1 and 3 share a picture). */
enum dave_pose {
    POSE_UNSET = 0,          /* no sprite chosen yet (g_dave_sprite 0 before the first level) */
    POSE_FRONT = 1,          /* g_spr_dave_front / g_mask_dave_front */
    POSE_WALK_LEFT = 2,      /* g_sprite_sets[9] / [10] */
    POSE_WALK_RIGHT = 3,     /* g_sprite_sets[11] / [12] */
    POSE_JUMP_LEFT = 4,      /* g_spr_jump_left / g_mask_jump_left */
    POSE_JUMP_RIGHT = 5,     /* g_spr_jump_right / g_mask_jump_right */
    POSE_CLIMB = 6,          /* g_sprite_sets[7] / [8] */
    POSE_JET_RIGHT = 7,      /* g_sprite_sets[3] / [4] */
    POSE_JET_LEFT = 8,       /* g_sprite_sets[5] / [6] */
};

#endif
