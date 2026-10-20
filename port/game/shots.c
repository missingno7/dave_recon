#include "shots.h"
#include "level_probe.h"

#define SHOT_STEP 2               /* pixels per tick */
#define SHOT_ANIM_TICKS 3         /* frame advance period (shared countdown) */
#define VIEW_RIGHT_EDGE 0x140     /* 320: kind-1 shots beyond it are dropped */

void shot_draw(const struct game *g, int i, struct frame_output *out)
{
    const struct shot *s = &g->shots[i];
    switch (s->kind) {
    case SHOT_KIND_MONSTER:
        out_draw(out, DRAW_XOR_SPRITE, s->x, s->y,
                 s->dir == SHOT_LEFT ? SPRITE_SHOT_LEFT : SPRITE_SHOT_RIGHT, s->frame);
        break;
    case SHOT_KIND_DAVE:
        out_draw(out, DRAW_XOR_SPRITE, s->x, s->y,
                 s->dir == SHOT_LEFT ? SPRITE_SHOT_B0 : SPRITE_SHOT_B1, 0);
        break;
    }
}

int shot_owner_exists(const struct game *g, int16_t owner)
{
    for (int i = 0; i < SHOT_COUNT; i++)
        if (g->shots[i].active == 1 && g->shots[i].owner == owner)
            return 1;
    return 0;
}

void shot_spawn(struct game *g, const struct resources *r, int16_t x, int16_t y,
                int16_t dir, int16_t kind, int16_t owner, struct frame_output *out)
{
    if (tile_attr_at_offset(g, r, x, y, 0, 1) == 1)
        return;                            /* would start inside a wall */
    for (int i = 0; i < SHOT_COUNT; i++) {
        struct shot *s = &g->shots[i];
        if (s->active != 0)
            continue;
        s->active = 1;
        s->x = x;
        s->y = y;
        s->owner = owner;
        s->dir = dir;
        s->frame = 0;
        s->kind = kind;
        /* frame 0 of the kind-0 sprites for any kind but 1 (unlike draw_object) */
        int set = dir == SHOT_LEFT ? SPRITE_SHOT_LEFT : SPRITE_SHOT_RIGHT;
        if (kind == SHOT_KIND_DAVE)
            set = dir == SHOT_LEFT ? SPRITE_SHOT_B0 : SPRITE_SHOT_B1;
        out_draw(out, DRAW_XOR_SPRITE, x, y, set, 0);
        return;
    }
}

void shots_step(struct game *g, const struct resources *r, struct frame_output *out)
{
    for (int i = 0; i < SHOT_COUNT; i++) {
        struct shot *s = &g->shots[i];
        if (s->active != 1)
            continue;
        int16_t step, probe_dx;
        if (s->dir == SHOT_LEFT) {
            step = -SHOT_STEP;
            probe_dx = -2;                 /* the pixel column just ahead on the left */
        } else if (s->dir == SHOT_RIGHT) {
            step = SHOT_STEP;
            probe_dx = 16;                 /* just past the 16-pixel sprite */
        } else {
            continue;                      /* switch without default: no effect at all */
        }
        if (tile_attr_at_offset(g, r, s->x, s->y, probe_dx, 1) == 1) {
            s->active = 0;
            shot_draw(g, i, out);          /* erase (after deactivating) */
            continue;
        }
        shot_draw(g, i, out);              /* erase at the old place */
        if (--g->shot_anim_count == 0) {   /* shared by all shots (quirk, see header) */
            g->shot_anim_count = SHOT_ANIM_TICKS;
            s->frame = (int16_t)((s->frame + 1) & 3);
        }
        s->x = (int16_t)(s->x + step);
        if (s->kind == SHOT_KIND_DAVE && (s->x < 0 || s->x > VIEW_RIGHT_EDGE)) {
            s->active = 0;                 /* left the view: dropped, nothing to erase */
            continue;
        }
        shot_draw(g, i, out);              /* draw at the new place */
    }
}
