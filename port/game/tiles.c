/*
 * Level tile lookups: tile_at, tile_attr_at, tile_attr_at_offset (DAVE.C
 * F_2C70.. region) and the level-byte addressing they share.
 *
 * Quirks reproduced on purpose (docs/UNDERSTANDING_LEDGER.md U-M1):
 *  - item 2: columns are never range-checked; the original indexes the flat
 *    100-column map, so column 100 is the next row's column 0, column -1 the
 *    previous row's last, and past the map it reads the record's 24 trailing
 *    bytes and then the next level's path. level_byte() reads exactly those
 *    bytes from the resources.
 *  - item 2: the row offset comes from the 10-entry table RowTimes100; rows
 *    10..19 (tile_at accepts 10 and 11; tile_attr_at_offset checks nothing)
 *    read the table after it (TileRowOfs: (row - 9) * 640) and rows 20..29
 *    the one after that (VgaTileRowOfs: (row - 19) * 5120); negative rows read
 *    the table before it (LevelOfs: (row + 10) * 1280). row_offset() keeps
 *    those values as named constant data.
 *  - item 3: tile bytes are signed and index g_tile_attr unchecked; every
 *    real map byte is 0..52, so only level -1 leaves the table (D4 stand-in 0).
 *  - pixel -> tile: C division truncates toward zero (x = -2 maps to the scroll
 *    column, not the one before).
 */
#include "world.h"

#define LEVEL_BYTES (LEVEL_COUNT * LEVEL_RECORD_BYTES)
#define MAP_BYTES (LEVEL_ROWS * LEVEL_COLS)
#define TILE_KINDS 53

/* g_tile_attr: 0 free, 1 solid, 2 deadly */
static const int16_t tile_attr_table[TILE_KINDS] = {
    0, 1, 0, 1, 0, 1, 2, 2, 2, 2, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1,
    2, 2, 2, 2, 1, 1, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0};

int16_t tile_attribute(int16_t tile)
{
    if (tile < 0 || tile >= TILE_KINDS)
        return 0;    /* outside g_tile_attr: level -1 only (U-M1 item 3), D4 stand-in */
    return tile_attr_table[tile];
}

int32_t row_offset(int16_t row)
{
    if (row >= 0 && row <= 9)
        return row * LEVEL_COLS;                  /* RowTimes100 */
    if (row >= 10 && row <= 19)
        return (row - 9) * 640;                   /* TileRowOfs, read past RowTimes100 */
    if (row >= 20 && row <= 29)
        return (int16_t)((row - 19) * 16 * 320);  /* VgaTileRowOfs (16-bit words) */
    if (row >= -10 && row <= -1)
        return (row + 10) * LEVEL_RECORD_BYTES;   /* LevelOfs, read before RowTimes100 */
    return INT32_MIN;   /* further tables: never reached by any probe of a real level (D4) */
}

int8_t level_byte(const struct game *g, const struct resources *r, int32_t offset)
{
    if (offset >= 0 && offset < MAP_BYTES)
        return g->level.map[offset / LEVEL_COLS][offset % LEVEL_COLS];
    if (g->level.index < 0 || g->level.index >= LEVEL_COUNT || offset == INT32_MIN)
        return 0;    /* D4 stand-in */
    /* position inside the original's g_levels array (10 records of 0x500 bytes) */
    int32_t at = (int32_t)g->level.index * LEVEL_RECORD_BYTES + LEVEL_PATH_BYTES + offset;
    if (at < 0 || at >= LEVEL_BYTES)
        return 0;    /* outside g_levels: D4 stand-in */
    const struct level_record *rec = &r->levels[at / LEVEL_RECORD_BYTES];
    int32_t within = at % LEVEL_RECORD_BYTES;
    if (within < LEVEL_PATH_BYTES)
        return rec->path[within];
    within -= LEVEL_PATH_BYTES;
    if (within < MAP_BYTES)   /* another level's record: pristine (the live one is restored on leaving) */
        return rec->map[within / LEVEL_COLS][within % LEVEL_COLS];
    return rec->tail[within - MAP_BYTES];
}

static int8_t probe(const struct game *g, const struct resources *r, int16_t row, int16_t col)
{
    int32_t ro = row_offset(row);
    return level_byte(g, r, ro == INT32_MIN ? INT32_MIN : ro + col);
}

/* Pixel (x, y) relative to Dave -> level tile. y is relative to the top of
 * the screen; the map starts 16 px down. 16-bit int arithmetic throughout. */
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

int16_t tile_attr_at_offset(const struct game *g, const struct resources *r,
                            int16_t x, int16_t y, int16_t dx, int16_t dy)
{
    /* no range checks at all (U-M1 item 2) */
    int16_t col = (int16_t)((int16_t)(dx + x) / 16 + g->level.scroll_x);
    int16_t row = (int16_t)((int16_t)(y + dy - 16) / 16);
    return tile_attribute(probe(g, r, row, col));
}
