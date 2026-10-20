/*
 * check_collisions (DAVE.C cs 0x35ED, census F_37ED): Dave against monsters,
 * Dave's shot against monsters, monster shots against Dave.
 *
 * Quirks reproduced on purpose:
 *  - box tests use UNSIGNED 16-bit differences (state-model section 6):
 *    `d < w` covers 0 <= d < w and `-d < w` covers -w < d < 0; the monster
 *    size tables are int16 values compared as unsigned (`width > -a`);
 *  - pass 1 does not stop at the first hit: once Dave's state is masked to
 *    0xC0 the loop goes on, so two overlapping monsters both die and Dave
 *    gets two explosions (the second re-arms the death timer);
 *  - pass 3 re-reads the alive bit, so a monster touch in pass 1 prevents a
 *    shot hit in the same tick; passes 2 and 3 end with `i = 4`;
 *  - a monster touch leaves Dave's state 0 (alive bit and movement cleared,
 *    0x40 kept if set), a monster shot sets exactly 0x40 (U-G1);
 *  - monsters at x >= 320 (off the right of the view) are never hit; there is
 *    no left-edge test.
 */
#include "monsters.h"
#include "world.h"

#define VIEW_WIDTH 0x140
#define DAVE_W 13            /* Dave's box: 0 <= dx < 13 / 16 tall */
#define DAVE_H 16
#define COLLISION_SOUND 8

const int16_t monster_width[8] = {28, 21, 22, 22, 14, 12, 16, 14};   /* levels 3..10 */
const int16_t monster_height[8] = {15, 18, 22, 20, 5, 8, 15, 16};

/* g_monster_width/height[level - 2]: only levels 2..9 have monsters that
 * these tests can reach (levels 0 and 1 have none, level -1's are never
 * `active == 1`); anything else is the D4 stand-in 0. */
static uint16_t box_w(const struct game *g)
{
    int k = g->level.index - 2;
    return (uint16_t)(k >= 0 && k < 8 ? monster_width[k] : 0);
}

static uint16_t box_h(const struct game *g)
{
    int k = g->level.index - 2;
    return (uint16_t)(k >= 0 && k < 8 ? monster_height[k] : 0);
}

void check_collisions(struct game *g, const struct resources *r, struct frame_output *out)
{
    (void)r;
    /* 1. Dave touches a monster: both die */
    if (g->level.index >= 2 && (g->dave.state & DAVE_ALIVE)) {
        for (int i = 0; i < MONSTER_COUNT; i++) {
            struct monster *m = &g->monsters[i];
            if (m->active == 0 || m->x >= VIEW_WIDTH)
                continue;
            uint16_t a = (uint16_t)(m->x - g->dave.x);
            uint16_t d = (uint16_t)(m->y - g->dave.y);
            if ((a < DAVE_W || box_w(g) > (uint16_t)-a) && (d < DAVE_H || box_h(g) > (uint16_t)-d)) {
                g->dave.state &= 0xC0;
                out_draw(out, DRAW_XOR_SPRITE, m->x, m->y, SPRITE_MONSTER,
                         monster_sprite_index(g->level.index, m->shown_frame));
                m->active = 0;
                out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0);
                spawn_explosion(g, g->dave.x, (int16_t)(g->dave.y + 3), EXPLOSION_DAVE, out);
                spawn_explosion(g, m->x, m->y, (int16_t)(i + 1), out);
                out_sound(out, COLLISION_SOUND);
            }
        }
    }
    /* 2. Dave's shot hits a monster: 100 points per level number */
    if (shot_owner_exists(g, SHOT_OWNER_DAVE)) {
        for (int i = 0; i < MONSTER_COUNT; i++) {
            struct monster *m = &g->monsters[i];
            if (m->active != 1 || m->x >= VIEW_WIDTH)
                continue;
            struct shot *s = &g->shots[find_object(g, SHOT_OWNER_DAVE)];
            uint16_t a = (uint16_t)(s->x - m->x);
            uint16_t b = (uint16_t)(s->y - m->y);
            if (((uint16_t)-a < 6 || box_w(g) > a) && ((uint16_t)-b < 3 || box_h(g) > b)) {
                out_draw(out, DRAW_XOR_SPRITE, m->x, m->y, SPRITE_MONSTER,
                         monster_sprite_index(g->level.index, m->shown_frame));
                out_draw(out, DRAW_XOR_SPRITE, s->x, s->y, s->dir == 1 ? SPRITE_SHOT_B1 : SPRITE_SHOT_B0, 0);
                s->active = 0;
                m->active = 0;
                spawn_explosion(g, m->x, m->y, (int16_t)(i + 1), out);
                out_sound(out, COLLISION_SOUND);
                /* int multiply, sign-extended into the unsigned long score */
                g->score += (uint32_t)(int32_t)(int16_t)((g->level.index + 1) * 100);
                update_score(g, out);
                break;                                   /* i = 4 */
            }
        }
    }
    /* 3. a monster's shot hits Dave */
    if (g->dave.state & DAVE_ALIVE) {
        for (int i = 0; i < MONSTER_COUNT; i++) {
            if (!shot_owner_exists(g, (int16_t)(i + 1)))
                continue;
            struct shot *s = &g->shots[find_object(g, (int16_t)(i + 1))];
            uint16_t b = (uint16_t)(s->x - g->dave.x);
            uint16_t c = (uint16_t)(s->y - g->dave.y);
            if (((uint16_t)-b < 16 || b < 13) && ((uint16_t)-c < 3 || c < 16)) {
                /* animated monster shot: set 2 flying left, set 1 right */
                out_draw(out, DRAW_XOR_SPRITE, s->x, s->y, s->dir == 0 ? SPRITE_SHOT_LEFT : SPRITE_SHOT_RIGHT, s->frame);
                s->active = 0;
                out_sound(out, COLLISION_SOUND);
                out_draw(out, DRAW_ERASE_DAVE, 0, 0, 0, 0);
                spawn_explosion(g, g->dave.x, (int16_t)(g->dave.y + 3), EXPLOSION_DAVE, out);
                g->dave.state = DAVE_KILLED;
                break;                                   /* i = 4 */
            }
        }
    }
}
