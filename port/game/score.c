/*
 * Score, extra lives and the status bar: update_score (DAVE.C cs 0x0A34),
 * draw_level_number, draw_status_meter, draw_status_bar, draw_inventory.
 *
 * Quirks kept (state-model section 6):
 *  - the extra-life test is `score - next_extra_life >= 20000` in unsigned
 *    32-bit arithmetic, and next_extra_life is rounded DOWN to a multiple of
 *    20000 of the current score (a jump of 40000 points still gives one life);
 *  - the life is only awarded (icon, sound) while lives < 3, but the goal
 *    advances regardless;
 *  - the 99999 cap is applied AFTER the extra-life test.
 */
#include "world.h"

#define EXTRA_LIFE_POINTS 20000u
#define SCORE_CAP 99999u
#define MAX_LIVES_SHOWN 3

enum { STATUS_JETPACK = 0, STATUS_GUN = 1, STATUS_TROPHY = 5, STATUS_LIFE = 6 };

void update_score(struct game *g, struct frame_output *out)
{
    if (g->score - g->next_extra_life >= EXTRA_LIFE_POINTS) {   /* uint32_t: wraps */
        g->next_extra_life = g->score / EXTRA_LIFE_POINTS * EXTRA_LIFE_POINTS;
        if (g->lives < MAX_LIVES_SHOWN) {
            out_draw(out, DRAW_XOR_SPRITE, g->lives * 16 + 0x100, 0, SPR_STATUS, STATUS_LIFE);
            g->lives++;
            out_sound(out, 0xC);
        }
    }
    if (g->score > SCORE_CAP)
        g->score = SCORE_CAP;
    /* five zero-padded digits at x = 0x40 .. 0x60 */
    uint32_t s = g->score;
    int digits[5];
    for (int k = 4; k >= 0; k--) {
        digits[k] = (int)(s % 10);
        s /= 10;
    }
    for (int k = 0; k < 5; k++)
        out_draw(out, DRAW_PIC, 0x40 + 8 * k, 1, PIC_DIGIT, digits[k]);
}

void draw_level_number(const struct game *g, struct frame_output *out)
{
    int n = g->level.index + 1;    /* int division/modulo truncate toward zero */
    out_draw(out, DRAW_PIC, 0xB0, 1, PIC_DIGIT, n / 10);
    out_draw(out, DRAW_PIC, 0xB8, 1, PIC_DIGIT, n % 10);
}

void draw_status_meter(const struct game *g, struct frame_output *out)
{
    out_draw(out, DRAW_XOR_SPRITE, 0x48, 0xAA, SPR_METER_LABEL, 0);
    for (int i = 0; i < g->inv.jetpack_fuel; i++)
        out_draw(out, DRAW_XOR_SPRITE, i * 2 + 0x4C, 0xAE, SPR_METER_BAR, 0);
}

void draw_status_bar(const struct game *g, struct frame_output *out)
{
    out_draw(out, DRAW_XOR_SPRITE, 0, 0, SPR_STATUS, 4);
    out_draw(out, DRAW_XOR_SPRITE, 0x78, 0, SPR_STATUS, 3);
    out_draw(out, DRAW_XOR_SPRITE, 0xC8, 0, SPR_STATUS, 2);
    for (int i = 0; i < g->lives; i++)
        out_draw(out, DRAW_XOR_SPRITE, i * 16 + 0x100, 0, SPR_STATUS, STATUS_LIFE);
}

void draw_inventory(struct game *g, struct frame_output *out)
{
    if (g->inv.has_jetpack) {
        draw_status_meter(g, out);
        out_draw(out, DRAW_XOR_SPRITE, 0, 0xAA, SPR_STATUS, STATUS_JETPACK);
    }
    if (g->inv.has_gun)
        out_draw(out, DRAW_XOR_SPRITE, 0xF0, 0xAA, SPR_STATUS, STATUS_GUN);
    if (g->inv.got_trophy)
        out_draw(out, DRAW_XOR_SPRITE, 0x48, 0xB8, SPR_STATUS, STATUS_TROPHY);
    update_score(g, out);
    draw_level_number(g, out);
}
