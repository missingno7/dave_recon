/*
 * Creating explosions: spawn_explosion (DAVE.C cs 0x1630). Their per-tick
 * update is update_explosions (lane N1, explosions.c); shots are created by
 * shot_spawn (= spawn_object, shots.c).
 *
 * Quirk kept: a full table silently drops the new explosion (and for Dave's
 * explosion the death timer is then not armed).
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
        out_draw(out, DRAW_XOR_SPRITE, x, y, SPRITE_EXPLOSION, 0);
        if (type == EXPLOSION_DAVE)
            g->dave.death_timer = DEATH_TIMER_TICKS;
        return;
    }
}
