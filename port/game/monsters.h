/*
 * Monsters (g_monsters, U-G5): path walking, animation and firing.
 *
 * Original: move_monsters (src/DAVE.C, census F_2D87), pipeline call after
 * update_explosions. Each active monster takes one path step every 5th
 * tick: it is erased with the frame it was last drawn with (shown_frame,
 * the mode-independent form of g_monsters.sprite, D3), moved by the next
 * signed (dx, dy) byte pair of the level's 256-byte path (0xEA = -22
 * restarts it), redrawn with its current anim_frame, its frame advances
 * every 2nd step, and it may fire.
 *
 * Quirks reproduced on purpose:
 * - The sprite is chosen BEFORE the frame advances, so the frame drawn lags
 *   anim_frame by one step every other step; shown_frame keeps the drawn
 *   one for the next erase (state-model section 5).
 * - path_pos is an unsigned 16-bit byte index read through a huge pointer
 *   with no bound: only a 0xEA in an even position restarts the path, and a
 *   path without one would run on into the map (U-M1 item 1; reproduced by
 *   level_record_byte). The restart test looks only at the dx byte.
 * - Countdowns are int16: a move_count imported as 0 or negative counts down
 *   through the int16 range before the next step, as in the original.
 * - Firing needs, in this C short-circuit order: 0 <= x < 0x154 (in view),
 *   no live shot of this monster (owner i + 1), then the fire countdown
 *   is decremented and must be < 1, then Dave alive (state bit 0x20). The
 *   countdown is therefore only decremented while the monster is in view
 *   without a shot, but also while Dave is dead (then it keeps going
 *   below 1 and the monster fires on the first tick Dave is alive again).
 * - The shot starts 16 px left of the monster when it is right of Dave
 *   (x > dave.x), else at x + width, at y + height / 2 - 2 (int division);
 *   width/height are g_monster_width/height[level - 2] (levels 3..10). For
 *   level indices 0, 1 and -1 the original reads the neighbouring constant
 *   tables; monster_size_window keeps those words so the lookup stays
 *   exact (no corpus level has an active monster there).
 * - spawn_object refuses a start inside a solid tile; the fire countdown
 *   has been reloaded regardless.
 */
#ifndef DAVE_MONSTERS_H
#define DAVE_MONSTERS_H

#include "output.h"
#include "resources.h"
#include "state.h"

/* move_monsters(): one step of every monster. */
void monsters_step(struct game *g, const struct resources *r, struct frame_output *out);

/* Index of a monster frame in the SPRITE_MONSTER set (output.h). */
static inline int monster_sprite_index(int16_t level, int16_t frame)
{
    return (level - 2) * 4 + frame;
}

#endif
