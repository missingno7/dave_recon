#include "explosions.h"
#include "level_probe.h"

#define EXPLOSION_FRAME_TICKS 13   /* the frame advances every 13th tick */
#define EXPLOSION_FALL_STEP 2      /* pixels sunk per frame change */
#define EXPLOSION_FLOOR_Y 0x98     /* no sinking from here down */

void explosions_step(struct game *g, const struct resources *r, struct frame_output *out)
{
    for (int i = 0; i < EXPLOSION_COUNT; i++) {
        struct explosion *e = &g->explosions[i];
        if (e->active != 1)
            continue;
        if (--e->life > 0) {
            int16_t x = e->x, y = e->y;
            out_draw(out, DRAW_XOR_SPRITE, x, y, SPRITE_EXPLOSION, e->frame);   /* erase */
            if (--e->anim == 0) {
                e->frame = (int16_t)((e->frame + 1) & 3);
                e->anim = EXPLOSION_FRAME_TICKS;
            }
            if (e->anim == EXPLOSION_FRAME_TICKS &&
                tile_attr_at_offset(g, r, x, y, 4, 14) != 1 &&
                tile_attr_at_offset(g, r, x, y, 14, 14) != 1 &&
                y < EXPLOSION_FLOOR_Y) {
                e->y = (int16_t)(e->y + EXPLOSION_FALL_STEP);
                y = (int16_t)(y + EXPLOSION_FALL_STEP);
            }
            out_draw(out, DRAW_XOR_SPRITE, x, y, SPRITE_EXPLOSION, e->frame);   /* redraw */
        } else {
            e->active = 0;
            out_draw(out, DRAW_XOR_SPRITE, e->x, e->y, SPRITE_EXPLOSION, e->frame);   /* erase */
        }
    }
}
