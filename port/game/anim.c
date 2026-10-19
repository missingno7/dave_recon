#include "anim.h"

void anim_step(struct anim_state *a, int16_t scroll_x, anim_redraw_fn redraw, void *ctx)
{
    if (--a->tick_divider != 0)
        return;
    a->tick_divider = ANIM_TICKS_PER_FRAME;
    for (int i = 0; i < ANIM_MAX_TILES && a->tiles[i].count > 0; i++) {
        struct anim_tile *t = &a->tiles[i];
        if (!t->active)
            continue;
        /* 16-bit int arithmetic, as in the original (values here are small
         * tile ids, so no wrap-around is observable). */
        t->cur = (int16_t)(t->cur + 1);
        if (t->cur >= t->first + t->count)
            t->cur = t->first;
        if (t->col >= scroll_x && t->col <= scroll_x + VIEW_COLUMNS - 1 && redraw)
            redraw(ctx, t->col - scroll_x, t->row, t->cur);
    }
}
