/*
 * F_2D38 -- tile_attr_at_offset(x, y, dx, dy)
 * cs [0x2b38,0x2b87) / file [0x2d38,0x2d87), 79 bytes.
 * Strict match: tools/match_function.py.
 *
 * Attribute word (DS:0x02CC[tile]) of the level tile at pixel
 * (x + dx, y + dy), column relative to the scroll column DS:0x57A0, row 0
 * starting at pixel 16. No range checks.
 *
 * @name tile_attr_at_offset
 */
/* @flags -G */

extern int D_57A0;              /* first visible level column */
extern char *D_57A8;            /* current level tile grid */
extern int D_13DD[];            /* row -> byte offset into the tile grid */
extern int D_02CC[];            /* tile id -> tile attribute */

int F_2D38(int x, int y, int dx, int dy)
{
    register int col, row;

    col = (dx + x) / 16 + D_57A0;
    row = (y + dy - 16) / 16;
    return D_02CC[(D_57A8 + D_13DD[row])[col]];
}
