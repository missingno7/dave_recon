/*
 * Dave-relative tile lookups: tile_at and tile_attr_at (DAVE.C F_2C70 ..
 * F_2CD8), built on level_probe.c (the flat g_levels reads and the
 * g_tile_attr window, shared with tile_attr_at_offset).
 *
 * Quirks reproduced on purpose (docs/UNDERSTANDING_LEDGER.md U-M1):
 *  - item 2: columns are never range-checked; the original indexes the flat
 *    100-column map, so column 100 is the next row's column 0, column -1 the
 *    previous row's last, and past the map it reads the record's trailing
 *    bytes and then the next level's path (level_record_byte);
 *  - item 2: tile_at accepts rows 10 and 11, whose RowTimes100[row] is read
 *    past the 10-entry table, from TileRowOfs: (row - 9) * 640, i.e. map
 *    offsets 640 and 1280 (row_offset keeps those values; the further tables
 *    are listed for completeness, no caller reaches them);
 *  - item 3: tile bytes are signed and index g_tile_attr unchecked
 *    (tile_attribute's window);
 *  - pixel -> tile: C division truncates toward zero (x = -2 maps to the scroll
 *    column, not the one before).
 */
#include "level_probe.h"
#include "world.h"

int8_t map_byte(const struct game *g, const struct resources *r, int32_t offset)
{
    if (offset == INT32_MIN)
        return 0;
    return level_record_byte(g, r, LEVEL_PATH_BYTES + offset);
}

static int8_t probe(const struct game *g, const struct resources *r, int16_t row, int16_t col)
{
    int32_t ro = row_offset(row);
    return map_byte(g, r, ro == INT32_MIN ? INT32_MIN : ro + col);
}

/* Pixel (x, y) relative to Dave -> level cell. The map starts 16 px down.
 * 16-bit int arithmetic throughout. */
static void dave_relative_cell(const struct game *g, int16_t x, int16_t y, int16_t *row, int16_t *col)
{
    *col = (int16_t)((int16_t)(x + g->dave.x) / 16 + g->level.scroll_x);
    *row = (int16_t)((int16_t)(g->dave.y + y - 16) / 16);
}

int16_t tile_attr_at(const struct game *g, const struct resources *r, int16_t x, int16_t y)
{
    int16_t row, col;
    if ((int16_t)(g->dave.y + y) < 16)
        return 0;
    dave_relative_cell(g, x, y, &row, &col);
    if (row > 9)
        return 0;
    return tile_attribute(probe(g, r, row, col));
}

int16_t tile_at(const struct game *g, const struct resources *r, int16_t x, int16_t y)
{
    int16_t row, col;
    if ((int16_t)(g->dave.y + y) < 16)
        return 0;
    dave_relative_cell(g, x, y, &row, &col);
    if (row > 11)        /* rows 10 and 11 are accepted: they read past the map (U-M1 item 2) */
        return 0;
    return probe(g, r, row, col);
}
