#include "monsters.h"
#include "level_probe.h"
#include "shots.h"

#define MONSTER_MOVE_TICKS 5     /* one path step every 5th tick */
#define MONSTER_ANIM_STEPS 2     /* the frame advances every 2nd step */
#define PATH_RESTART (-22)       /* 0xEA as a signed path byte */
#define FIRE_VIEW_RIGHT 0x154    /* a monster fires only while 0 <= x < 0x154 */

/* g_level_start_y[10], g_monster_width[8], g_monster_height[8] as they lie
 * in the original data segment (contiguous), so that [level - 2] for level
 * indices -1, 0 and 1 reads the same words the original reads. */
static const int16_t monster_size_window[26] = {
    144, 144, 96, 96, 144, 144, 48, 144, 32, 144,   /* g_level_start_y */
    28, 21, 22, 22, 14, 12, 16, 14,                 /* g_monster_width, levels 3..10 */
    15, 18, 22, 20, 5, 8, 15, 16,                   /* g_monster_height, levels 3..10 */
};

static int16_t monster_width(int16_t level)  { return monster_size_window[10 + level - 2]; }
static int16_t monster_height(int16_t level) { return monster_size_window[18 + level - 2]; }

void monsters_step(struct game *g, const struct resources *r, struct frame_output *out)
{
    int16_t level = g->level.index;
    for (int i = 0; i < MONSTER_COUNT; i++) {
        struct monster *m = &g->monsters[i];
        if (m->active == 0 || --m->move_count != 0)
            continue;
        m->move_count = MONSTER_MOVE_TICKS;
        out_draw(out, DRAW_XOR_SPRITE, m->x, m->y, SPRITE_MONSTER,
                 monster_sprite_index(level, m->shown_frame));          /* erase */

        uint16_t pos = m->path_pos;
        if (level_record_byte(g, r, pos) == PATH_RESTART) {
            m->path_pos = 0;
            pos = 0;
        }
        m->x = (int16_t)(m->x + level_record_byte(g, r, pos));
        m->y = (int16_t)(m->y + level_record_byte(g, r, (int32_t)pos + 1));
        m->path_pos = (uint16_t)(m->path_pos + 2);

        m->shown_frame = m->anim_frame;
        out_draw(out, DRAW_XOR_SPRITE, m->x, m->y, SPRITE_MONSTER,
                 monster_sprite_index(level, m->shown_frame));          /* draw */
        if (--m->anim_count == 0) {
            m->anim_count = MONSTER_ANIM_STEPS;
            m->anim_frame = (int16_t)((m->anim_frame + 1) & 3);
        }

        if (m->x < FIRE_VIEW_RIGHT && m->x >= 0 && !shot_owner_exists(g, (int16_t)(i + 1)) &&
            --m->fire_count < 1 && (g->dave.state & DAVE_ALIVE)) {
            m->fire_count = m->reload;
            int16_t y = (int16_t)(m->y + monster_height(level) / 2 - 2);
            if (m->x > g->dave.x)
                shot_spawn(g, r, (int16_t)(m->x - 16), y, SHOT_LEFT, SHOT_KIND_MONSTER,
                           (int16_t)(i + 1), out);
            else
                shot_spawn(g, r, (int16_t)(m->x + monster_width(level)), y, SHOT_RIGHT,
                           SHOT_KIND_MONSTER, (int16_t)(i + 1), out);
        }
    }
}
