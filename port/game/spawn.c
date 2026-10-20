/*
 * Creating explosions and shots: spawn_explosion (DAVE.C cs 0x1630) and
 * spawn_object (cs 0x4686). Their per-tick updates are update_explosions /
 * move_bullets (lane N1).
 *
 * Quirks kept: a full table silently drops the new object (no explosion, no
 * shot, and for Dave's explosion no death timer); spawn_object refuses a
 * shot whose start pixel (x, y + 1) is inside a solid tile.
 */
#include "world.h"

#define EXPLOSION_LIFE 0x6E   /* ticks */
#define EXPLOSION_FRAME_TICKS 0xD
#define DEATH_TIMER_TICKS 300

void spawn_explosion(struct game *g, int16_t x, int16_t y, int16_t type, struct frame_output *out)
{
    for (int i = 0; i < EXPLOSION_COUNT; i++) {
        struct explosion *e = &g->explosions[i];
        if (e->active != 0)
            continue;
        e->x = x;
        e->y = y;
        e->type = type;
        e->active = 1;
        e->frame = 0;
        e->life = EXPLOSION_LIFE;
        e->anim = EXPLOSION_FRAME_TICKS;
        out_draw(out, DRAW_XOR_SPRITE, x, y, 0, 0);   /* g_sprite_sets[0][mode][0] */
        if (type == EXPLOSION_DAVE)
            g->dave.death_timer = DEATH_TIMER_TICKS;
        return;
    }
}

void spawn_object(struct game *g, const struct resources *r, int16_t x, int16_t y,
                  int16_t dir, int16_t kind, int16_t owner, struct frame_output *out)
{
    if (tile_attr_at_offset(g, r, x, y, 0, 1) == 1)
        return;
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
        /* the sprite draw_object would use: monster shots animate (sets 1/2,
         * frame 0), Dave's (kind 1) are static */
        if (kind == 1)
            out_draw(out, DRAW_XOR_SPRITE, x, y, dir == 0 ? SPR_SHOT_B0 : SPR_SHOT_B1, 0);
        else
            out_draw(out, DRAW_XOR_SPRITE, x, y, dir == 0 ? 2 : 1, 0);
        return;
    }
}
