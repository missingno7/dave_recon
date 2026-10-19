/*
 * What one game step produces besides the new state (state-model.md D1):
 * the ordered list of draw commands and the sound requests, exactly in the
 * order the original issued the corresponding calls. The game layer never
 * draws or plays anything itself; port/present applies draw commands to its
 * persistent logical framebuffer, and the sound scheduler consumes requests.
 *
 * Commands are LOGICAL: sprites are named by (set, index) into the original
 * per-mode sprite tables, not by a mode-specific id (D3); the presentation
 * layer resolves them for the selected video mode. Each op documents the
 * original routine it mirrors and the meaning of its arguments.
 */
#ifndef DAVE_OUTPUT_H
#define DAVE_OUTPUT_H

#include <stdint.h>

enum draw_op {
    DRAW_TILE = 1,        /* DrawTile(view_col, row, tile): a = view column, b = row, c = tile id */
    /* Further ops are added with the subsystem that first needs them; each
     * must name its original routine (C function or asm proc) and arguments. */
};

struct draw_cmd {
    uint8_t op;           /* enum draw_op */
    int16_t a, b, c, d;
};

#define OUTPUT_MAX_DRAWS 4096
#define OUTPUT_MAX_SOUNDS 64

struct frame_output {
    uint16_t n_draws;
    uint16_t n_sounds;
    struct draw_cmd draws[OUTPUT_MAX_DRAWS];
    int16_t sounds[OUTPUT_MAX_SOUNDS];    /* PlaySound(n) requests, in order */
};

static inline void out_draw(struct frame_output *o, uint8_t op, int a, int b, int c, int d)
{
    if (o && o->n_draws < OUTPUT_MAX_DRAWS) {
        struct draw_cmd *cmd = &o->draws[o->n_draws++];
        cmd->op = op;
        cmd->a = (int16_t)a; cmd->b = (int16_t)b; cmd->c = (int16_t)c; cmd->d = (int16_t)d;
    }
}

static inline void out_sound(struct frame_output *o, int n)
{
    if (o && o->n_sounds < OUTPUT_MAX_SOUNDS)
        o->sounds[o->n_sounds++] = (int16_t)n;
}

#endif
