/*
 * The world: tile lookups, collisions, pickups, scoring, level loading,
 * level completion, warps and the attract mode (native-port lane N3).
 *
 * Each pipeline call keeps the original's algorithm and order of effects;
 * drawing becomes draw commands (output.h) in the original call order, sounds
 * go through out_sound. Calls that wait for retraces add them to
 * out->retraces, and every wait is written as an explicit loop over retraces
 * whose input comes from `struct world_io` (polled with the number of
 * retraces waited so far in this call), so the per-retrace restructuring of
 * state-model D2 is mechanical.
 *
 * Originals (src/DAVE.C, census ids): check_collisions F_37ED, pick_up_items
 * F_3FD5, level_complete F_3BA3, check_warp_transition F_34CB, attract_mode
 * F_09DE, load_level F_4E69, init_game_state F_535A, spawn_explosion,
 * spawn_object, update_score, tile_at / tile_attr_at / tile_attr_at_offset,
 * wait_for_input, draw_actors, redraw_screen, show_high_scores.
 */
#ifndef DAVE_WORLD_H
#define DAVE_WORLD_H

#include <stdint.h>
#include "output.h"
#include "resources.h"
#include "state.h"

/* ---- input seen by the waiting loops (D2, D7) ---- */

struct wait_input {          /* get_player_input(1) */
    int16_t dir;             /* 0..7 clockwise from north, 8 = none */
    int16_t fire, jump;
};

/* `retrace` is the number of retraces this call has waited so far
 * (out->retraces when the original polls). */
struct world_io {
    void *ctx;
    struct wait_input (*player)(void *ctx, uint32_t retrace);   /* get_player_input(1) */
    int16_t  (*key_peek)(void *ctx, uint32_t retrace);   /* bioskey(1): 0 = no key waiting,
                                                            else scan << 8 | ascii */
    void     (*key_take)(void *ctx, uint32_t retrace);   /* bioskey(0) */
    uint32_t (*clock)(void *ctx, uint32_t retrace);      /* time(NULL), Borland time_t (D7) */
};

/* ---- tile lookups (U-M1 items 2 and 3) ---- */

/* Byte `offset` of the level data, relative to the first tile of the live
 * map (row * 100 + column). Offsets outside the map read what the original
 * reads there: the neighbouring records' path / tiles / trailing bytes of
 * g_levels; outside g_levels, and on level -1, the documented stand-in 0
 * (state-model D4). */
int8_t  level_byte(const struct game *g, const struct resources *r, int32_t offset);
/* g_tile_attr[tile]: 0 free, 1 solid, 2 deadly (tiles outside 0..52: 0, D4) */
int16_t tile_attribute(int16_t tile);
/* Row -> offset as the original's RowTimes100[row] reads it, including the
 * neighbouring tables for rows outside 0..9 (U-M1 item 2). */
int32_t row_offset(int16_t row);

int16_t tile_at(const struct game *g, const struct resources *r, int16_t x, int16_t y);
int16_t tile_attr_at(const struct game *g, const struct resources *r, int16_t x, int16_t y);
int16_t tile_attr_at_offset(const struct game *g, const struct resources *r,
                            int16_t x, int16_t y, int16_t dx, int16_t dy);

/* ---- objects ---- */

#define SHOT_OWNER_DAVE 5

static inline int16_t find_object(const struct game *g, int16_t owner)
{
    for (int i = 0; i < SHOT_COUNT; i++)
        if (g->shots[i].active == 1 && g->shots[i].owner == owner)
            return (int16_t)i;
    return -1;
}

static inline int16_t object_exists(const struct game *g, int16_t owner)
{
    return find_object(g, owner) >= 0;
}

#define EXPLOSION_DAVE 5     /* spawn_explosion type that arms the death timer */

void spawn_explosion(struct game *g, int16_t x, int16_t y, int16_t type, struct frame_output *out);
void spawn_object(struct game *g, const struct resources *r, int16_t x, int16_t y,
                  int16_t dir, int16_t kind, int16_t owner, struct frame_output *out);

/* ---- score and status bar ---- */

void update_score(struct game *g, struct frame_output *out);
void draw_level_number(const struct game *g, struct frame_output *out);
void draw_status_meter(const struct game *g, struct frame_output *out);
void draw_status_bar(const struct game *g, struct frame_output *out);
void draw_inventory(struct game *g, struct frame_output *out);

/* ---- levels ---- */

void init_game_state(struct game *g, struct frame_output *out);
void load_level(struct game *g, const struct resources *r, struct frame_output *out);
/* movmem(g_tiles, g_level, 1000): put the pristine map back into the live one */
void restore_level_map(struct game *g, const struct resources *r);
void draw_actors(const struct game *g, struct frame_output *out);
void redraw_screen(struct game *g, struct frame_output *out);
void wait_for_input(struct game *g, const struct world_io *io, struct frame_output *out);
void show_high_scores(int with_sound, struct frame_output *out);

/* ---- pipeline calls ---- */

void check_collisions(struct game *g, const struct resources *r, struct frame_output *out);
void pick_up_items(struct game *g, const struct resources *r, struct frame_output *out);
void level_complete(struct game *g, const struct resources *r, const struct world_io *io,
                    struct frame_output *out);
void check_warp_transition(struct game *g, const struct resources *r, const struct world_io *io,
                           struct frame_output *out);
void attract_mode(struct game *g, const struct resources *r, const struct world_io *io,
                  struct frame_output *out);

/* ---- constant tables (game_constant, DAVE.C initialised data) ---- */

extern const int16_t monster_width[8];   /* g_monster_width, indexed level - 2 */
extern const int16_t monster_height[8];  /* g_monster_height */

#endif
