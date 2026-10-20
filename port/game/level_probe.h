/*
 * Reads of the current level record as the original addresses it: the
 * monster path (g_level_path, a huge pointer to the record start) and the
 * tile probe tile_attr_at_offset (DAVE.C, census F_2D38).
 *
 * The original indexes one flat array, g_levels (10 records of 0x500 bytes:
 * 256-byte path, 10x100 map, 24 trailing bytes), with no range checks, so a
 * path without its 0xEA terminator runs on into the map, and a probe column
 * outside 0..99 reaches the neighbouring row, the path bytes before the map
 * or the trailing bytes and the next record after it (U-M1 item 2). Those
 * reads are reproduced here byte for byte from the live map (current level)
 * and the level resources (path, trailer, other records). The tile byte is
 * signed and indexes g_tile_attr without a check (U-M1 item 3): bytes
 * outside 0..52 read the constant words around the table, given as
 * tile_attr_window below.
 *
 * Outside the contract (decision D4): addresses before g_levels or after its
 * last record (only the level -1 warp, U-M3, gets there) read as 0, and a
 * probe row outside 0..9 (RowTimes100 has 10 entries) reads attribute 0.
 * No corpus tick reaches either; see the callers for why the row case is
 * unobservable in update_explosions.
 */
#ifndef DAVE_LEVEL_PROBE_H
#define DAVE_LEVEL_PROBE_H

#include <stdint.h>
#include "resources.h"
#include "state.h"

/* Byte at `offset` from the start of the current level's record, as the
 * original's flat g_levels array holds it (live map for the current level). */
int8_t level_record_byte(const struct game *g, const struct resources *r, int32_t offset);

/* tile_attr_at_offset(x, y, dx, dy): collision attribute (0 free, 1 solid,
 * 2 deadly) of the map tile at view pixel (x + dx, y + dy); row 0 starts at
 * pixel 16. Column = (x + dx) / 16 + scroll_x, row = (y + dy - 16) / 16,
 * both truncating toward zero (a pixel at -15..-1 maps to column/row 0). */
int16_t tile_attr_at_offset(const struct game *g, const struct resources *r,
                            int16_t x, int16_t y, int16_t dx, int16_t dy);

/* g_tile_attr[tile] for a signed tile byte, including the constant words
 * around the table that out-of-range bytes read (U-M1 item 3). Shared by
 * tile_attr_at (world lane, tiles.c). */
int16_t tile_attribute(int8_t tile);

#endif
