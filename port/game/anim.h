/*
 * Animated level tiles (gems, fire, water, ...).
 *
 * Original: animate_tiles() in src/DAVE.C (census F_332C), called once per
 * game tick from main's pipeline. Every 10th tick each active animated tile
 * advances to its next frame, wrapping from first + count back to first;
 * tiles inside the visible window are redrawn.
 *
 * Native split: anim_step() updates the simulation state only; the redraw of
 * visible tiles is reported through a callback, so presentation stays out of
 * the game layer.
 */
#ifndef DAVE_ANIM_H
#define DAVE_ANIM_H

#include <stdint.h>

#define ANIM_MAX_TILES 200      /* capacity of the original table */
#define ANIM_TICKS_PER_FRAME 10 /* the frame advances every 10th game tick */
#define VIEW_COLUMNS 20         /* visible level columns: scroll .. scroll+19 */

struct anim_tile {
    int16_t active;   /* 0 = slot unused (tile picked up / destroyed) */
    int16_t first;    /* first tile id of the animation */
    int16_t cur;      /* current tile id */
    int16_t col;      /* level column (0..99) */
    int16_t row;      /* level row (0..9) */
    int16_t count;    /* frames in the animation; a record with count <= 0 ends the list */
};

struct anim_state {
    struct anim_tile tiles[ANIM_MAX_TILES];
    int16_t tick_divider;     /* counts down from ANIM_TICKS_PER_FRAME */
};

/* Called for each visible tile whose frame changed: view column (0..19),
 * level row, new tile id. */
typedef void (*anim_redraw_fn)(void *ctx, int view_col, int row, int tile);

void anim_step(struct anim_state *a, int16_t scroll_x, anim_redraw_fn redraw, void *ctx);

#endif
