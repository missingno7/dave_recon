/*
 * TEST-ONLY: mapping between struct game and the original DGROUP layout
 * (DS 0x0000-0x9F20 snapshots from tools/oracle.py). Addresses come from
 * docs/semantic-inventory.json (tests/test_native.py cross-checks them).
 * Never include this from game/, present/ or platform/ code.
 */
#ifndef DAVE_DGROUP_MAP_H
#define DAVE_DGROUP_MAP_H

#include "resources.h"
#include "state.h"

#define DGROUP_LEN 0x9F20

/* Import every modelled field of `g` from the snapshot `m`. */
void dgroup_import(struct game *g, const unsigned char *m);
/* Export every modelled field of `g` into `m` (a copy of the pre-state
 * snapshot, so unmodelled bytes keep their original values). */
void dgroup_export(const struct game *g, unsigned char *m);

/* Fill the immutable resources from a snapshot: g_levels (DS 0x173A, 10 x
 * 0x500). The current level's map may carry pickup edits, so its pristine
 * copy is taken from g_tiles (DS 0x615C) instead. */
void dgroup_import_resources(struct resources *r, const unsigned char *m);

/* ---- world (N3) additions ---- */

/* After dgroup_import/dgroup_import_resources: the level resources from
 * `pristine_levels` (g_levels as DAVE.EXE initialises it, 10 x 0x500 bytes)
 * when given (else the snapshot's, as dgroup_import_resources took them);
 * and level.pristine_loaded from g_tiles (all zero = never loaded). */
void dgroup_import_world(struct game *g, struct resources *r, const unsigned char *m,
                         const unsigned char *pristine_levels);
/* Regenerate the bytes the native game derives from the level resources:
 * every g_levels record other than the current one gets its pristine map
 * (the original restores a level's record when it leaves it), and g_tiles
 * the pristine map of the current level (zeros before the first load).
 * Level -1 (state-model D4): g_tiles is left as it is. Call before
 * dgroup_export. */
void dgroup_export_levels(const struct game *g, const struct resources *r, unsigned char *m);
/* Platform input visible in a snapshot: the INT 9 key table g_keydown,
 * the key bindings g_key_scans and the player-1 input device. */
struct dgroup_keyboard {
    int16_t keydown[128];
    uint8_t scans[10];
    int16_t device;
};
void dgroup_import_keyboard(struct dgroup_keyboard *k, const unsigned char *m);

#endif
