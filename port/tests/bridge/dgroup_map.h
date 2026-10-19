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

#endif
