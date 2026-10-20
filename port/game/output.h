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

    /* --- world (N3): collisions, items, levels, warps, attract mode --- */
    DRAW_PIC = 20,        /* draw_tile(x, y, tile) -> DrawPic*: a = x px, b = y px,
                             c = enum pic_table, d = index (digits, title animation) */
    DRAW_ERASE_DAVE = 22, /* erase_dave(): restore the background saved under Dave */
    DRAW_DAVE = 23,       /* draw_dave(): a = x, b = y; save-under, then Dave's current sprite
                             (the last DRAW_SET_DAVE_SPRITE) */
    DRAW_SET_DAVE_SPRITE = 24, /* g_dave_sprite/g_dave_mask assignment (presentation, D3):
                             a = sprite set of the image (mask = set a + 1), b = frame;
                             a = -1: the front-facing pose g_spr_dave_front/g_mask_dave_front;
                             a = -2 / -3: g_spr_jump_left / g_spr_jump_right (+ their masks).
                             Emitted together with game.dave.pose by dave_set_pose (player.c) */
    DRAW_LEVEL_VIEW = 25, /* DrawLevelView(): a = level index, b = scroll column; the 20x10
                             view of the live map (level_live_map(g): no world call edits the
                             map after this command within the same step) */
    DRAW_VIEW_BORDERS = 26, /* DrawViewBorders() */
    DRAW_SET_VIDEO_MODE = 27, /* set_video_mode(g_video_mode) (+ CacheEGATiles in EGA):
                             clears the screen */
    DRAW_TEXT_CURSOR = 28,/* g_text_x = a, g_text_y = b, g_text_left = c; -1 = unchanged */
    DRAW_TEXT_XOR = 29,   /* XorMask = a (0 or -1) */
    DRAW_PRINT_STRING = 30, /* print_string(text): a = enum text_id, b = parameter
                             (TEXT_GOOD_WORK: the digit of "N more to go") */
    DRAW_CENTERED_WINDOW = 31, /* draw_centered_window(w, h): a = w, b = h */
    DRAW_HISCORE_ROW = 33,/* show_high_scores' row a: score digits, initials, level of
                             DSCORES.DAV entry a at the current text cursor */
};

/* Picture tables addressed by DRAW_PIC (c). */
enum pic_table {
    PIC_DIGIT = 0,        /* g_tile_digit0[mode] + index */
    PIC_TITLE_ANIM = 1,   /* g_title_anim_tiles[mode * 4 + index] */
};

/* Texts printed by DRAW_PRINT_STRING (DAVE.C string pool, in order of use). */
enum text_id {
    TEXT_GOOD_WORK = 1,   /* "good work! only N more to go!" (b = N) */
    TEXT_LAST_LEVEL,      /* "  this is the last level!!!" */
    TEXT_FINISHED,        /* " yes! you finished the game!" */
    TEXT_CONGRATS_1,      /* the ending's 10 strings, "         congratulations!..." */
    TEXT_CONGRATS_2, TEXT_CONGRATS_3, TEXT_CONGRATS_4, TEXT_CONGRATS_5,
    TEXT_CONGRATS_6, TEXT_CONGRATS_7, TEXT_CONGRATS_8, TEXT_CONGRATS_9,
    TEXT_CONGRATS_10,     /* "           press space" */
    TEXT_TITLE_BY,        /* "     BY JOHN ROMERO\n\r" */
    TEXT_TITLE_COPYRIGHT, /* " (C) 1990 SOFTDISK, INC.\n\r" */
    TEXT_TITLE_HELP,      /* "PRESS THE F1 KEY FOR HELP" */
    TEXT_HIGH_SCORES,     /* "High Scores\r\n\nScore  Name  Level\r\n-----  ----  -----\r\n" */
    TEXT_ROW_BREAK,       /* "\n\n\r" */
};

/* Sound control requests (out_sound with a negative code), in call order
 * among the PlaySound(n >= 0) requests. */
enum sound_control {
    SOUND_STOP = -1,      /* StopSound() */
    SOUND_PAUSE = -2,     /* PauseSound() */
    SOUND_RESUME = -3,    /* ResumeSound() */
    SOUND_WAIT = -4,      /* WaitSound(): block until the playing sound has ended */
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
    /* world (N3): status bar and warp tube */
    SPRITE_STATUS = 16,       /* g_status_tiles[mode * g_status_row_len + index]: 0 jetpack,
                                 1 gun, 2..4 labels, 5 trophy ("go thru the door"), 6 life */
    SPRITE_WARP_LEFT = 17,    /* g_spr_warp_left[mode] (index 0) */
    SPRITE_WARP_RIGHT = 18,   /* g_spr_warp_right[mode] */
    SPRITE_METER_LABEL = 19,  /* g_spr_meter_label[mode]: jetpack fuel meter frame */
    SPRITE_METER_BAR = 20,    /* g_spr_meter_bar[mode]: one fuel unit */
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
