/*
 * F_2C70 -- tile_attr_at(x, y)
 * cs [0x2a70,0x2ad8) / file [0x2c70,0x2cd8), 104 bytes.
 * Strict match: tools/match_function.py.
 *
 * Returns the attribute word (table DS:0x02CC indexed by tile id) of the
 * level tile under screen pixel (x, y). Pixel y is relative to the playfield
 * offset DS:0x56EC and the first 16 pixels are above the grid; rows > 9 are
 * outside the 10-row playfield; both cases return 0. Column = (x + DS:0x56EA)
 * / 16 + DS:0x57A0 (the scroll column). The tile byte is read (signed) from
 * the grid at DS:0x57A8 via the row-offset table DS:0x13DD.
 *
 * @name tile_attr_at
 */

extern int D_56EA;              /* horizontal pixel scroll / x offset */
extern int D_56EC;              /* vertical pixel offset (g_start_y) */
extern int D_57A0;              /* first visible level column */
extern char *D_57A8;            /* current level tile grid */
extern int D_13DD[];            /* row -> byte offset into the tile grid */
extern int D_02CC[];            /* tile id -> tile attribute */
int F_2C70(int x, int y)
{
    register int row, col;

    if (D_56EC + y < 16)
        return 0;
    col = (x + D_56EA) / 16 + D_57A0;
    row = (D_56EC + y - 16) / 16;
    if (row > 9)
        return 0;
    return D_02CC[(D_57A8 + D_13DD[row])[col]];
}
