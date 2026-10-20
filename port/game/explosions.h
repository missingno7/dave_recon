/*
 * Explosions: the short-lived actors spawned for Dave's death and for killed
 * monsters (g_actors, U-G6/U-G7).
 *
 * Original: update_explosions (src/DAVE.C, census F_18F6), pipeline call
 * after move_dave. spawn_explosion (F_1830) belongs to the collisions/world
 * worker (N3).
 *
 * Quirks reproduced on purpose:
 * - Each living explosion is erased with its old frame and redrawn with the
 *   new one, both XOR (draw = erase).
 * - The fall test runs only on the tick whose 13-tick countdown just
 *   reloaded (anim == 13 after the step), so an explosion sinks 2 px per
 *   frame change, not per tick, while both probes below it, at (x+4, y+14)
 *   and (x+14, y+14), are not solid (attribute != 1: deadly tiles let it
 *   sink) and y < 0x98. The two probes run before the y test (C order);
 *   for y >= 0x98 their result cannot matter, which is why a probe row
 *   outside the map is unobservable here (level_probe.h).
 * - The last tick of its life (life counts 110 -> 0) erases it at its
 *   stored position with its current frame and frees it; the frame and
 *   countdown are left as they are (only .active changes).
 * - The sprite index is g_sprite_sets[0][0][mode * 4 + frame], flat; frame
 *   is always 0..3 (& 3), so it is set 0, mode, frame.
 */
#ifndef DAVE_EXPLOSIONS_H
#define DAVE_EXPLOSIONS_H

#include "output.h"
#include "resources.h"
#include "state.h"

/* update_explosions(): one step of every active explosion. */
void explosions_step(struct game *g, const struct resources *r, struct frame_output *out);

#endif
