/*
 * Shots: the monsters' bullets (kind 0) and Dave's (kind 1), g_shots.
 *
 * Originals (src/DAVE.C):
 *   move_bullets   (census F_301B) -> shots_step
 *   draw_object    (F_3205)        -> shot_draw
 *   object_exists  (F_483F)        -> shot_owner_exists
 *   spawn_object   (F_4886)        -> shot_spawn
 *
 * spawn_object is owned by the collisions/world worker (N3); this is the
 * same routine, needed here because move_monsters fires through it. Merge
 * the two into one definition.
 *
 * Quirks reproduced on purpose:
 * - One animation countdown for all shots (g_shot_anim_count, U-G6): it is
 *   decremented once per moving shot, so with two shots alive each animates
 *   at a different phase and every frame step goes to whichever shot
 *   reaches the 0.
 * - Only kind-1 shots (Dave's) are dropped when they leave the view
 *   (x < 0 or x > 320, tested after the move, without an erase at the new
 *   position because none was drawn); monster shots fly on off-screen until
 *   a probe finds a solid tile (U-G6, U-M1 item 2: those probes may leave
 *   the map, see level_probe.h).
 * - A blocked shot is deactivated first and then erased (draw_object does
 *   not look at .active).
 * - A shot whose dir is neither 0 nor 1 is never moved or drawn; a kind
 *   other than 0 or 1 moves but is never drawn by draw_object, although
 *   spawn_object draws it once with the kind-0 sprite.
 * - draw_object indexes g_sprite_sets[set][0][mode * 4 + frame] flat: frame
 *   is always 0..3 (spawned 0, advanced & 3), so it is set[mode][frame].
 */
#ifndef DAVE_SHOTS_H
#define DAVE_SHOTS_H

#include "output.h"
#include "resources.h"
#include "state.h"

enum { SHOT_KIND_MONSTER = 0, SHOT_KIND_DAVE = 1 };
enum { SHOT_LEFT = 0, SHOT_RIGHT = 1 };
#define SHOT_OWNER_DAVE 5

/* move_bullets(): one step of every active shot. */
void shots_step(struct game *g, const struct resources *r, struct frame_output *out);

/* draw_object(i): XOR-draw shot i with the sprite for its kind/dir/frame. */
void shot_draw(const struct game *g, int i, struct frame_output *out);

/* object_exists(owner): 1 if an active shot belongs to `owner`. */
int shot_owner_exists(const struct game *g, int16_t owner);

/* spawn_object(x, y, dir, kind, owner): unless the tile at (x, y + 1) is
 * solid, fill the first free shot and draw it once. */
void shot_spawn(struct game *g, const struct resources *r, int16_t x, int16_t y,
                int16_t dir, int16_t kind, int16_t owner, struct frame_output *out);

#endif
