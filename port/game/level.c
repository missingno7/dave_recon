/*
 * Level set-up and the shared screen sequences: init_game_state (DAVE.C cs
 * 0x515A, census F_535A), load_level (cs 0x4C69, F_4E69), the map restore
 * (movmem(g_tiles, g_level, 1000)), draw_actors, redraw_screen and
 * wait_for_input.
 *
 * Quirks reproduced on purpose:
 *  - load_level re-seeds rand() with 100 on every load (U-S1): one draw per
 *    animated tile in map order (its start frame), then one per monster slot
 *    (start frame), so in-level randomness is the same on every load;
 *  - load_level clears only the `active` word of the 200 animated-tile
 *    records and terminates the new list with `count = 0` in the record after
 *    the last one: the other fields of unused records keep the previous
 *    level's values (observable state);
 *  - it copies the whole 80-byte monster block, then overwrites anim count,
 *    frame, move and fire counts of all four slots, active or not;
 *  - it drops gun, jetpack and trophy (their status icons are XOR-erased
 *    first) but keeps the jetpack fuel and fuel tick;
 *  - level -1 (the warp bug, U-M1 item 1 / U-M3): the start state, position
 *    and monster block are the bytes in front of the original tables, kept
 *    as named constants below; its map and path (DGROUP bytes including the
 *    sound driver's asynchronous variables) are outside the equivalence
 *    contract (state-model D4) and replaced by the documented stand-in: an
 *    all-zero map.
 *  - wait_for_input animates the level tiles 20 times per blink, so the
 *    animation state after it depends on when the input came (state-model D2).
 */
#include <string.h>
#include "anim.h"
#include "monsters.h"
#include "rng.h"
#include "world.h"
#include "player.h"   /* dave_set_pose */

#define LEVEL_SEED 100
#define ANIMATED_KINDS 4

/* game_constant tables (DAVE.C initialised data) */
static const uint8_t level_flags[LEVEL_COUNT] = {0x24, 0x24, 0x24, 0x28, 0x24, 0x24, 0x28, 0x24, 0x28, 0x24};
static const int16_t level_start_x[LEVEL_COUNT] = {32, 16, 32, 16, 32, 32, 16, 32, 96, 32};
static const int16_t level_start_y[LEVEL_COUNT] = {144, 144, 96, 96, 144, 144, 48, 144, 32, 144};
static const int16_t animated_tile_ids[ANIMATED_KINDS] = {6, 10, 25, 36};
static const int16_t animated_tile_frames[ANIMATED_KINDS] = {4, 5, 4, 5};

/* g_level_monster_init: per level, slot fields active, x (level pixels), y,
 * path start, reload. (The block's other five arrays are overwritten.) */
struct monster_init { int16_t active[4], x[4], y[4], path_pos[4], reload[4]; };
static const struct monster_init monster_init[LEVEL_COUNT] = {
    {{0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}},
    {{1, 1, 0, 0}, {951, 711, 0, 0}, {69, 69, 0, 0}, {0, 0, 0, 0}, {20, 20, 0, 0}},
    {{1, 0, 0, 0}, {515, 0, 0, 0}, {46, 0, 0, 0}, {0, 0, 0, 0}, {1, 0, 0, 0}},
    {{1, 1, 1, 1}, {240, 520, 788, 1472}, {60, 60, 66, 68}, {0, 0, 0, 0}, {10, 10, 10, 10}},
    {{1, 1, 1, 1}, {158, 457, 694, 662}, {142, 144, 142, 44}, {0, 0, 0, 0}, {10, 10, 10, 10}},
    {{1, 1, 1, 1}, {76, 259, 743, 855}, {48, 31, 60, 60}, {0, 0, 0, 0}, {25, 8, 8, 1}},
    {{1, 1, 1, 0}, {846, 1136, 1350, 0}, {100, 50, 40, 0}, {0, 0, 0, 0}, {5, 2, 2, 0}},
    {{1, 1, 1, 1}, {563, 709, 788, 1102}, {143, 143, 143, 143}, {0, 8, 0, 8}, {20, 10, 5, 10}},
    {{1, 1, 1, 1}, {709, 1040, 1323, 819}, {144, 64, 96, 44}, {0, 0, 0, 0}, {20, 20, 10, 10}},
};

/* Level -1 (U-M1 item 1): what the original reads in front of its tables.
 * g_level_flags[-1] = the high byte of g_jump_dy[46] = 0; g_level_start_x[-1]
 * = the word made of g_level_flags[8..9] = 0x2428; g_level_start_y[-1] =
 * g_level_start_x[9] = 32; the monster block = the last 80 bytes of
 * g_sprite_sets (sets 9..12, words 116..155). */
#define LEVEL_M1_FLAGS 0x00
#define LEVEL_M1_START_X 0x2428
#define LEVEL_M1_START_Y 32
static const struct monster_init level_m1_monsters = {
    {57, 58, 59, 58}, {75, 77, 79, 77}, {97, 101, 105, 101}, {64, 65, 66, 65}, {53, 55, 57, 55}};

static int level_valid(int16_t index)
{
    return index >= 0 && index < LEVEL_COUNT;
}

void level_start_position(int16_t level, uint16_t *state, int16_t *x, int16_t *y)
{
    int valid = level_valid(level);
    *state = valid ? level_flags[level] : LEVEL_M1_FLAGS;
    *x = valid ? level_start_x[level] : LEVEL_M1_START_X;
    *y = valid ? level_start_y[level] : LEVEL_M1_START_Y;
}

void level_maps_init(struct game *g, const struct resources *r)
{
    /* program start (the original's g_levels as DAVE.EXE loads it) */
    for (int lv = 0; lv < LEVEL_COUNT; lv++)
        memcpy(g->level_maps[lv], r->levels[lv].map, LEVEL_ROWS * LEVEL_COLS);
    memset(g->stray_map, 0, sizeof g->stray_map);
    memset(g->level.backup, 0, sizeof g->level.backup);
    g->level.pristine_loaded = 0;
}

void restore_level_map(struct game *g, const struct resources *r)
{
    (void)r;
    /* movmem(g_tiles, g_level, 1000): the backup (all zero before the first
     * load_level) goes back into the live record */
    memcpy(level_live_map(g), g->level.backup, LEVEL_ROWS * LEVEL_COLS);
}

void init_game_state(struct game *g, struct frame_output *out)
{
    for (int i = 0; i < LEVEL_COUNT; i++)
        g->level.warp_used[i] = 0;
    g->lives = 3;
    g->score = 0;
    g->next_extra_life = 0;
    g->game_over = 0;
    g->level.index = 0;
    g->level.scroll_x = 0;
    g->anim.tick_divider = ANIM_TICKS_PER_FRAME;
    g->level.in_warp_zone = 0;
    out_draw(out, DRAW_SET_VIDEO_MODE, 0, 0, 0, 0);
}

void load_level(struct game *g, const struct resources *r, struct frame_output *out)
{
    int16_t L = g->level.index;
    int valid = level_valid(L);

    g->level.done = 0;
    rng_srand(g, LEVEL_SEED);
    level_start_position(L, &g->dave.state, &g->dave.x, &g->dave.y);
    g->dave.move_throttle = 3;
    g->dave.anim_delay = 2;
    dave_set_pose(g, POSE_FRONT, 0, out);
    g->dave.anim_frame = 0;
    g->dave.input_dir = 8;
    g->dave.facing = 1;
    g->shot_anim_count = 3;
    for (int i = 0; i < EXPLOSION_COUNT; i++)
        g->explosions[i].active = 0;
    for (int i = 0; i < SHOT_COUNT; i++)
        g->shots[i].active = 0;
    for (int i = 0; i < ANIM_MAX_TILES; i++)
        g->anim.tiles[i].active = 0;

    /* the live map is the level's record as it stands (D8: edits that escaped
     * a restore persist, N2-6); g_tiles gets its copy at the END of the
     * original load_level, after the animated tiles are scanned */
    int8_t (*live)[LEVEL_COLS] = level_live_map(g);

    /* animated tiles, in map order, each with a random start frame */
    int n = 0;
    for (int row = 0; row < LEVEL_ROWS; row++) {
        for (int col = 0; col < LEVEL_COLS; col++) {
            int16_t tile = live[row][col];               /* signed char */
            for (int k = 0; k < ANIMATED_KINDS; k++) {
                if (animated_tile_ids[k] != tile)
                    continue;
                struct anim_tile *t = &g->anim.tiles[n];
                t->active = 1;
                t->first = tile;
                t->cur = (int16_t)(tile + rng_scaled(g, animated_tile_frames[k]));
                t->col = (int16_t)col;
                t->row = (int16_t)row;
                t->count = animated_tile_frames[k];
                /* terminator; at most 84 animated tiles per level, so n + 1 < 200 (U-M1 item 6) */
                if (n + 1 < ANIM_MAX_TILES)
                    g->anim.tiles[n + 1].count = 0;
                n++;
            }
        }
    }

    const struct monster_init *mi = valid ? &monster_init[L] : &level_m1_monsters;
    for (int i = 0; i < MONSTER_COUNT; i++) {
        struct monster *m = &g->monsters[i];
        m->active = mi->active[i];
        m->x = mi->x[i];
        m->y = mi->y[i];
        m->path_pos = (uint16_t)mi->path_pos[i];
        m->reload = mi->reload[i];
    }
    for (int i = 0; i < MONSTER_COUNT; i++) {
        struct monster *m = &g->monsters[i];
        m->anim_count = 2;
        m->anim_frame = rng_scaled(g, 3);
        m->move_count = 5;
        m->fire_count = m->reload;
        m->shown_frame = 0;            /* g_monsters.sprite = frame 0 of this level (D3) */
    }

    /* movmem(g_level, g_tiles, 1000): back up the live record */
    memcpy(g->level.backup, live, LEVEL_ROWS * LEVEL_COLS);
    g->level.pristine_loaded = 1;
    g->level.scroll_x = 0;
    if (g->inv.has_gun == 1)
        out_draw(out, DRAW_XOR_SPRITE, 0xF0, 0xAA, SPRITE_STATUS, 1);
    if (g->inv.has_jetpack == 1) {
        draw_status_meter(g, out);
        out_draw(out, DRAW_XOR_SPRITE, 0, 0xAA, SPRITE_STATUS, 0);
    }
    g->inv.has_jetpack = 0;
    g->inv.got_trophy = 0;
    g->inv.has_gun = 0;
}

void draw_actors(const struct game *g, struct frame_output *out)
{
    if (g->dave.y > 15 && (g->dave.state & DAVE_ALIVE))
        out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
    for (int i = 0; i < MONSTER_COUNT; i++)
        if (g->monsters[i].active == 1)
            out_draw(out, DRAW_XOR_SPRITE, g->monsters[i].x, g->monsters[i].y, SPRITE_MONSTER,
                     monster_sprite_index(g->level.index, g->monsters[i].shown_frame));
    for (int i = 0; i < SHOT_COUNT; i++)
        if (g->shots[i].active == 1)
            shot_draw(g, i, out);
    for (int i = 0; i < EXPLOSION_COUNT; i++)
        if (g->explosions[i].active == 1)
            out_draw(out, DRAW_XOR_SPRITE, g->explosions[i].x, g->explosions[i].y, SPRITE_EXPLOSION,
                     g->explosions[i].frame);
}

/* the title logo: 7 rows x 10 columns of tiles (redraw_screen's local array) */
static const int8_t title_logo[7][10] = {
    {0x12, 0x00, 0x12, 0x12, 0x12, 0x12, 0x00, 0x12, 0x00, 0x12},
    {0x12, 0x00, 0x12, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x12},
    {0x12, 0x00, 0x12, 0x00, 0x00, 0x12, 0x12, 0x12, 0x00, 0x12},
    {0x12, 0x00, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x32, 0x12},
    {0x12, 0x00, 0x12, 0x06, 0x12, 0x12, 0x12, 0x00, 0x00, 0x12},
    {0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x12},
    {0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x06, 0x12},
};

void redraw_screen(struct game *g, struct frame_output *out)
{
    out_draw(out, DRAW_SET_VIDEO_MODE, 0, 0, 0, 0);
    if (g->mode < MODE_TITLE) {
        out_draw(out, DRAW_VIEW_BORDERS, 0, 0, 0, 0);
        draw_status_bar(g, out);
        draw_inventory(g, out);          /* update_score inside can award a pending extra life */
        out_draw(out, DRAW_LEVEL_VIEW, g->level.index, g->level.scroll_x, 0, 0);
        dave_set_pose(g, POSE_FRONT, 0, out);
        for (int i = 0; i < MONSTER_COUNT; i++)
            if (g->monsters[i].active)
                g->monsters[i].shown_frame = 0;   /* g_monsters.sprite reset to frame 0 */
        draw_actors(g, out);
        if (g->mode == MODE_SCORES)
            show_high_scores(0, out);
    }
    if (g->mode == MODE_TITLE) {
        out_draw(out, DRAW_TEXT_XOR, -1, 0, 0, 0);
        out_draw(out, DRAW_TEXT_CURSOR, 8, 6, 8, 0);
        out_draw(out, DRAW_PRINT_STRING, TEXT_TITLE_BY, 0, 0, 0);
        out_draw(out, DRAW_PRINT_STRING, TEXT_TITLE_COPYRIGHT, 0, 0, 0);
        out_draw(out, DRAW_TEXT_CURSOR, -1, 0x15, -1, 0);
        out_draw(out, DRAW_PRINT_STRING, TEXT_TITLE_HELP, 0, 0, 0);
        out_draw(out, DRAW_TEXT_XOR, 0, 0, 0, 0);
        for (int i = 0; i < 10; i++)
            for (int j = 0; j < 7; j++)
                out_draw(out, DRAW_TILE, i + 5, j + 3, title_logo[j][i], 0);
    }
}

void show_high_scores(int with_sound, struct frame_output *out)
{
    out_sound(out, SOUND_WAIT);
    if (with_sound)
        out_sound(out, 0xB);
    for (int i = 4; i < 0x1A; i += 2)
        out_draw(out, DRAW_CENTERED_WINDOW, i, i / 2, 0, 0);
    out_draw(out, DRAW_TEXT_CURSOR, 0x10, 6, 0xC, 0);
    out_draw(out, DRAW_PRINT_STRING, TEXT_HIGH_SCORES, 0, 0, 0);
    for (int i = 0; i < SCORE_ENTRIES; i++) {
        if (with_sound)
            out_sound(out, 6);
        out_draw(out, DRAW_HISCORE_ROW, i, 0, 0, 0);
        if (with_sound)
            out_sound(out, SOUND_WAIT);
    }
}

/* One WaitVBL followed by animate_tiles. */
static void wait_and_animate(struct game *g, struct frame_output *out)
{
    out->retraces++;
    anim_step(&g->anim, g->level.scroll_x, out);
}

void wait_for_input(struct game *g, const struct world_io *io, struct frame_output *out)
{
    if (io->key_peek(io->ctx, out->retraces))
        io->key_take(io->ctx, out->retraces);
    struct frame_input in;
    do {
        /* Dave blinks: 10 retraces hidden, 10 shown; the level keeps animating */
        out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0);
        for (int i = 0; i < 10; i++)
            wait_and_animate(g, out);
        out_draw(out, DRAW_DAVE, g->dave.x, g->dave.y, 0, 0);
        for (int i = 0; i < 10; i++)
            wait_and_animate(g, out);
        in = io->player(io->ctx, out->retraces);
    } while (in.dir == 8 && io->key_peek(io->ctx, out->retraces) == 0);
    if ((g->dave.state & DAVE_FALL) == DAVE_FALL)
        out_sound(out, 2);
}
