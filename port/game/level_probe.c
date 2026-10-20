#include "level_probe.h"

/* g_tile_attr[t] for every signed tile byte t = -128..127 (index t + 128).
 * Entries 128..180 are g_tile_attr[0..52] itself; the others are the
 * initialised constant words the unchecked index reads around it in the
 * original data segment (g_spr_shot_b0 ... g_tile_climbable before it,
 * g_spr_dave_front ... g_sprite_sets after it; U-M1 item 3). Real map bytes
 * are 0..52; the rest is only reached through out-of-range probes. Checked
 * against the original data by tests/test_native.py. */
static const int16_t tile_attr_window[256] = {
    203, 353, 128, 83, 113, 68, 81, 109, 67, 87, 121, 70, 85, 117, 69, 229,
    391, 148, 225, 226, 227, 228, 387, 388, 389, 390, 144, 145, 146, 147, 8, 213,
    214, 215, 216, 217, 218, 224, 0, 373, 374, 375, 376, 377, 378, 386, 0, 133,
    134, 135, 136, 137, 138, 143, 0, 2, 4, 20, 10, 47, 48, 49, 50, 51,
    52, 2000, 0, 0, 1000, 100, 50, 150, 300, 200, 500, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0,
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,
    0, 1, 0, 1, 0, 1, 2, 2, 2, 2, 0, 0, 0, 0, 0, 1,
    1, 1, 1, 1, 0, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1, 0,
    0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 59, 65, 56, 73, 93, 63, 221, 381, 141, 222, 382,
    142, 6, 10, 25, 36, 4, 5, 4, 5, 205, 207, 209, 211, 357, 361, 365,
    369, 129, 130, 131, 132, 189, 191, 193, 191, 325, 329, 333, 329, 121, 122, 123,
    122, 195, 197, 199, 197, 337, 341, 345, 341, 124, 125, 126, 125, 101, 103, 105,
    103, 149, 153, 157, 153, 77, 78, 79, 78, 113, 115, 117, 115, 173, 177, 181,
};

int8_t level_record_byte(const struct game *g, const struct resources *r, int32_t offset)
{
    /* position in the flat array of all records */
    int32_t flat = (int32_t)g->level.index * LEVEL_RECORD_BYTES + offset;
    if (flat < 0 || flat >= (int32_t)LEVEL_COUNT * LEVEL_RECORD_BYTES)
        return 0;                          /* outside g_levels: D4, see the header */
    int lv = (int)(flat / LEVEL_RECORD_BYTES);
    int at = (int)(flat % LEVEL_RECORD_BYTES);
    if (at < LEVEL_PATH_BYTES)
        return r->levels[lv].path[at];
    at -= LEVEL_PATH_BYTES;
    if (at < LEVEL_ROWS * LEVEL_COLS) {
        const int8_t *map = lv == g->level.index ? &g->level.map[0][0] : &r->levels[lv].map[0][0];
        return map[at];
    }
    return r->levels[lv].trailer[at - LEVEL_ROWS * LEVEL_COLS];
}

int16_t tile_attr_at_offset(const struct game *g, const struct resources *r,
                            int16_t x, int16_t y, int16_t dx, int16_t dy)
{
    /* 16-bit int arithmetic; C division truncates toward zero, like the
     * original's idiv (U-M1 item 2: no range checks). */
    int16_t col = (int16_t)((int16_t)(dx + x) / 16 + g->level.scroll_x);
    int16_t row = (int16_t)((int16_t)(y + dy - 16) / 16);
    if (row < 0 || row >= LEVEL_ROWS)
        return 0;                          /* RowTimes100[row] out of its table: D4 */
    /* (g_level + RowTimes100[row])[col]: one flat index, so a column outside
     * 0..99 lands in a neighbouring row or outside the map */
    int8_t tile = level_record_byte(g, r, LEVEL_PATH_BYTES + row * LEVEL_COLS + col);
    return tile_attr_window[tile + 128];
}
