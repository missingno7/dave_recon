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

/* ---- player (N2): Dave, the view, the sprite routines it calls ---------- */

/* Draw ops of the player subsystems, each named after the original routine
 * it mirrors (values continue DRAW_TILE's numbering). */
enum draw_op_player {
    DRAW_DAVE = 20,       /* draw_dave(): SaveUnder* the area under Dave's mask at (x, y), then
                             DrawMasked* his sprite. a = x, b = y, c = enum dave_pose, d = pose frame 0..3 */
    ERASE_DAVE = 21,      /* erase_dave(): RestoreUnder* the area saved by the last DRAW_DAVE. no args */
    DRAW_LEVEL_VIEW = 22, /* DrawLevelView() (tiles.asm): the 20 x 9.5-tile playfield from line 16,
                             tiles from the live level map as it is when the command is issued.
                             a = scroll_x (first visible column), b = level index */
    XOR_SPRITE = 23,      /* xor_sprite(x, y, sprite): DrawXor* (draws and erases). a = x, b = y,
                             c = enum sprite_table, d = index in that table's per-mode row */
};

/* Logical sprite references (state-model D3): the original's per-mode id
 * tables, resolved by present/ for the selected video mode. */
enum sprite_table {
    SPRITES_SET0 = 0,         /* g_sprite_sets[set][mode][index], set 0..12 (index 0..3) */
    SPRITES_SET12 = 12,
    SPRITES_STATUS = 13,      /* g_status_tiles[mode * g_status_row_len + index] */
    SPRITES_METER_LABEL = 14, /* g_spr_meter_label[mode] (index 0) */
    SPRITES_METER_BAR = 15,   /* g_spr_meter_bar[mode] (index 0) */
    SPRITES_SHOT_B0 = 16,     /* g_spr_shot_b0[mode]: Dave's bullet flying left */
    SPRITES_SHOT_B1 = 17,     /* g_spr_shot_b1[mode]: Dave's bullet flying right */
    SPRITES_MONSTER_SLOT = 18 /* the sprite last stored for monster slot `index` (g_monsters.sprite,
                                 D3-deferred: to become (level, shown frame) with the monster model) */
};

/* Sound requests other than PlaySound(n) (n >= 0), mirroring the driver
 * calls of lowlevel.asm, in the same ordered request list. */
enum sound_control {
    SOUND_STOP = -1,      /* StopSound() */
    SOUND_PAUSE = -2,     /* PauseSound(): remember the playing sound, then stop */
    SOUND_RESUME = -3,    /* ResumeSound(): continue the remembered sound */
};

#endif
