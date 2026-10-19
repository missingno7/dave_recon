/*
 * F_371F -- draw_inventory_row()
 * cs [0x351f,0x356e) / file [0x371f,0x376e), 79 bytes.
 * Strict match: tools/match_function.py.
 *
 * Draws a sprite at (0x48, 0xAA) taken from the per-graphics-mode table
 * DS:0x0342[DS:0x4F86], then DS:0x5798 copies of the per-mode sprite
 * DS:0x0348[DS:0x4F86] at x = 0x4C + 2*i, y = 0xAE (a horizontal meter on
 * the bottom status bar). F_1BD6 is the draw-sprite(x, y, id) routine.
 *
 * @name draw_status_meter
 */
/* @flags -G */

extern int D_4F86;              /* graphics-mode table index */
extern int D_0342[];
extern int D_0348[];
extern int D_5798;              /* meter length */

void F_1BD6(int x, int y, int sprite);

void F_371F(void)
{
    int i;

    F_1BD6(0x48, 0xaa, D_0342[D_4F86]);
    for (i = 0; i < D_5798; i++)
        F_1BD6(i * 2 + 0x4c, 0xae, D_0348[D_4F86]);
}
