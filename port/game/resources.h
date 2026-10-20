/*
 * Immutable game resources the simulation reads (never writes).
 *
 * Level records come from the original g_levels array (docs/data-layout.md,
 * codec tools/levels.py): per level a 256-byte monster path (signed dx,dy
 * pairs, 0xEA restarts the path) and the pristine 10x100 tile map. The live,
 * editable map is struct game.level.map; the pristine one here is what
 * load_level copies and what the original keeps in g_tiles.
 *
 * Who fills it: the platform layer from the user's DAVE.EXE data (via the
 * resource readers), or the test bridge from an oracle snapshot.
 */
#ifndef DAVE_RESOURCES_H
#define DAVE_RESOURCES_H

#include <stdint.h>
#include "state.h"

#define LEVEL_PATH_BYTES 256
#define DEMO_BANK_BYTES 4368     /* the demo segment, zero padding included */

struct level_record {
    int8_t path[LEVEL_PATH_BYTES];
    int8_t map[LEVEL_ROWS][LEVEL_COLS];
    /* The original's 24 trailing bytes per record (recorder leftovers in
     * the shipped data). Normally unread, but tile_at() accepts map rows 10
     * and 11 without a range check, and those flat indexes continue into
     * this tail and then into the NEXT record's path (player.c). */
    int8_t tail[24];
};

struct resources {
    struct level_record levels[LEVEL_COUNT];
    /* The attract-demo bank (far segment 0B31, format:demo_stream): u32
     * count, u32 offsets[count], per demo a start-level byte and the input
     * stream read by process_input through game.demo.pos (player.c). */
    uint8_t demo_bank[DEMO_BANK_BYTES];
};

#endif
