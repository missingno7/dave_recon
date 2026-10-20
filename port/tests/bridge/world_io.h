/* TEST-ONLY: input for the world's waiting loops, see world_io.c. */
#ifndef DAVE_BRIDGE_WORLD_IO_H
#define DAVE_BRIDGE_WORLD_IO_H

#include "resources.h"
#include "world.h"

/* Once: demo bank, pristine levels and the scenario inputs (environment,
 * see world_io.c). */
void bridge_world_load(struct resources *r);
/* Before each verified call, after dgroup_import/dgroup_import_resources:
 * snapshot `index` of the pre-state stream. Completes the level resources
 * and level.pristine_loaded (dgroup_import_world) and sets up the input. */
void bridge_world_begin(long index, const unsigned char *snap, struct game *g, struct resources *r);
const struct world_io *bridge_world_io(void);

#endif
