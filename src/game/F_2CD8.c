/*
 * F_2CD8 -- tile_at(x, y)
 * cs [0x2ad8,0x2b38) / file [0x2cd8,0x2d38), 96 bytes.
 * Strict match: tools/match_function.py.
 *
 * Same coordinate mapping as F_2C70 but returns the raw (signed char) tile
 * id under screen pixel (x, y), and accepts rows 0..11 (0 when y is above
 * the grid or the row is > 11).
 *
 * @name tile_at
 * Codegen: first declared register variable gets SI, the second DI.
 */

extern int D_56EA;              /* horizontal pixel scroll / x offset */
extern int D_56EC;              /* vertical pixel offset (g_start_y) */
extern int D_57A0;              /* first visible level column */
extern char *D_57A8;            /* current level tile grid */
extern int D_13DD[];            /* row -> byte offset into the tile grid */
int F_2CD8(int x, int y)
{
    register int row, col;

    if (D_56EC + y < 16)
        return 0;
    col = (x + D_56EA) / 16 + D_57A0;
    row = (D_56EC + y - 16) / 16;
    if (row > 11)
        return 0;
    return (D_57A8 + D_13DD[row])[col];
}
