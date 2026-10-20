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
#define LEVEL_TRAILER_BYTES 24
#define LEVEL_RECORD_BYTES (LEVEL_PATH_BYTES + LEVEL_ROWS * LEVEL_COLS + LEVEL_TRAILER_BYTES)  /* 0x500 */

struct level_record {
    int8_t path[LEVEL_PATH_BYTES];
    int8_t map[LEVEL_ROWS][LEVEL_COLS];
    int8_t trailer[LEVEL_TRAILER_BYTES]; /* the record's 24 trailing bytes: never read in
                                            range; tile probes past row 9 column 99 and
                                            monster paths without 0xEA reach them (U-M1 item 2) */
};

/* The attract-mode demo bank (format:demo_stream, docs/data-layout.md far
 * segment 0x0B31, codec tools/demos.py): u32 count, u32 offsets[count], then
 * per demo the start level byte and the input stream. */
#define DEMO_BANK_BYTES 4368

struct resources {
    struct level_record levels[LEVEL_COUNT];
    uint8_t demos[DEMO_BANK_BYTES];   /* demo bank, byte image */
};

#endif
