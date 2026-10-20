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

/* ---- player (N2) ---------------------------------------------------------- */
#include "input.h"
#include "input_map.h"

/* Dave's pose (D3) <-> g_dave_sprite / g_dave_mask (presentation ids, per
 * g_gfx_index). Called by dgroup_import / dgroup_export. */
void dgroup_import_player_view(struct game *g, const unsigned char *m);
void dgroup_export_player_view(const struct game *g, unsigned char *m);

/* Reconstruct the frame_input that get_player_input(1) returns in snapshot
 * `m`: the device g_input_device[1] (DS 0x12F2); for the keyboard,
 * g_keydown[128] (DS 0x8A32, ints) through the bindings g_key_scans
 * (DS 0x1310), decoded by platform/input_map.c (read_keyboard_input). Mouse
 * and joystick state is not in DGROUP: returns -1 for them. menu_key (the
 * BIOS keyboard buffer at 0040:001E) and dos_seconds are not in the
 * snapshot either and are 0. */
int dgroup_import_input(struct frame_input *in, const unsigned char *m);
/* The input settings of a snapshot (D6: outside struct game). */
void dgroup_import_input_settings(struct input_settings *s, const unsigned char *m);

/* (The demo bank is far data outside DGROUP: the bridge reads it from the
 * unpacked DAVE.EXE, bridge.c load_demo_bank.) */

#endif
