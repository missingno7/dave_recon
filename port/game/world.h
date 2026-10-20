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
#include "input.h"           /* struct frame_input: the logical input sample (N2) */
#include "level_probe.h"     /* tile_attr_at_offset, level_record_byte, tile_attribute (N1) */
#include "output.h"
#include "resources.h"
#include "shots.h"           /* shot_spawn = spawn_object, shot_owner_exists = object_exists (N1) */
#include "state.h"

/* ---- input seen by the waiting loops (D2, D7) ---- */

/* `retrace` is the number of retraces this call has waited so far
 * (out->retraces when the original polls). */
struct world_io {
    void *ctx;
    struct frame_input (*player)(void *ctx, uint32_t retrace);  /* get_player_input(1): dir,
                                                                  fire, jump (input.h) */
    int16_t  (*key_peek)(void *ctx, uint32_t retrace);   /* bioskey(1): 0 = no key waiting,
                                                            else scan << 8 | ascii */
    void     (*key_take)(void *ctx, uint32_t retrace);   /* bioskey(0) */
    uint32_t (*clock)(void *ctx, uint32_t retrace);      /* time(NULL), Borland time_t (D7) */
};

/* ---- tile lookups (U-M1 items 2 and 3) ---- */

/* Byte `offset` of the live map (row * 100 + column) as the original's flat
 * read reaches it, out-of-range offsets included (level_record_byte). */
int8_t  map_byte(const struct game *g, const struct resources *r, int32_t offset);
/* (row_offset: level_probe.h) */

int16_t tile_at(const struct game *g, const struct resources *r, int16_t x, int16_t y);
int16_t tile_attr_at(const struct game *g, const struct resources *r, int16_t x, int16_t y);

/* ---- objects ---- */

static inline int16_t find_object(const struct game *g, int16_t owner)
{
    for (int i = 0; i < SHOT_COUNT; i++)
        if (g->shots[i].active == 1 && g->shots[i].owner == owner)
            return (int16_t)i;
    return -1;
}

#define EXPLOSION_DAVE 5     /* spawn_explosion type that arms the death timer */

void spawn_explosion(struct game *g, int16_t x, int16_t y, int16_t type, struct frame_output *out);

/* ---- score and status bar ---- */

void update_score(struct game *g, struct frame_output *out);
void draw_level_number(const struct game *g, struct frame_output *out);
void draw_status_meter(const struct game *g, struct frame_output *out);
void draw_status_bar(const struct game *g, struct frame_output *out);
void draw_inventory(struct game *g, struct frame_output *out);

/* ---- levels ---- */

void init_game_state(struct game *g, struct frame_output *out);
/* g_level_flags / g_level_start_x / g_level_start_y [level]: Dave's state and
 * position at the start of a level (load_level, handle_death), level -1 incl. */
void level_start_position(int16_t level, uint16_t *state, int16_t *x, int16_t *y);
/* g_warp_start_scroll_x / g_warp_start_x [level]: where the warp zone entered
 * from `level` starts Dave (check_warp_transition, handle_death). */
void warp_start_position(int16_t level, int16_t *scroll_x, int16_t *x);
/* *(char far *)(g_demo_data + pos): a signed byte of the demo bank
 * (attract_mode, process_input); see attract.c for out-of-bank reads. */
int8_t demo_byte(const struct resources *r, int32_t pos);
void load_level(struct game *g, const struct resources *r, struct frame_output *out);
/* Program start: the live maps of all levels begin as the resource maps (D8). */
void level_maps_init(struct game *g, const struct resources *r);

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
