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
    DRAW_XOR_SPRITE = 2,  /* xor_sprite(x, y, sprite) (DAVE.C -> DrawXor{CGA,EGA,VGA}): XOR-blit,
                             so the same command both draws and erases. a = x, b = y (view
                             pixels), c = sprite set (enum sprite_set), d = index in the set */
    /* Further ops are added with the subsystem that first needs them; each
     * must name its original routine (C function or asm proc) and arguments. */
};

/* Logical sprite names for DRAW_XOR_SPRITE (D3): (set, index) resolved per
 * video mode by the presentation layer.
 *   0..12           = row of g_sprite_sets[13][3][4]; index = frame 0..3,
 *                     id = g_sprite_sets[set][mode][index]
 *   SPRITE_SHOT_B0/1 = g_spr_shot_b0[mode] / g_spr_shot_b1[mode]; index 0
 *   SPRITE_MONSTER  = the monster sprites move_monsters computes; index =
 *                     (level - 2) * 4 + frame, id = base[mode] + step[mode] *
 *                     index with base {0x7D, 0xC5, 0x59}, step {2, 4, 1}
 *                     (CGA, EGA, VGA) */
enum sprite_set {
    SPRITE_EXPLOSION = 0,     /* g_sprite_sets[0]: explosion actors */
    SPRITE_SHOT_RIGHT = 1,    /* g_sprite_sets[1]: kind-0 (monster) shot, dir != 0 */
    SPRITE_SHOT_LEFT = 2,     /* g_sprite_sets[2]: kind-0 (monster) shot, dir 0 */
    SPRITE_SHOT_B0 = 13,      /* g_spr_shot_b0: kind-1 (Dave's) shot, dir 0 */
    SPRITE_SHOT_B1 = 14,      /* g_spr_shot_b1: kind-1 (Dave's) shot, dir != 0 */
    SPRITE_MONSTER = 15,      /* per-level monster frames (move_monsters, redraw_screen, load_level) */
};

struct draw_cmd {
    uint8_t op;           /* enum draw_op */
    int16_t a, b, c, d;
};

#define OUTPUT_MAX_DRAWS 4096
#define OUTPUT_MAX_SOUNDS 64

struct frame_output {
    uint16_t retraces;    /* vertical retraces the original waited for during this
                             call (WaitVBL count); explicit so the per-retrace
                             restructuring (state-model.md D2) stays mechanical */
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
