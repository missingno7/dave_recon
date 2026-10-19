/*
 * F_376E -- draw_status_bar()
 * cs [0x356e,0x35ed) / file [0x376e,0x37ed), 127 bytes.
 * Strict match: tools/match_function.py.
 *
 * Draws the top status line: three label sprites at x = 0, 0x78, 0xC8
 * (y = 0) and one life icon per remaining life (DS:0x56EE = g_lives) at
 * x = 0x100 + 16*i. Sprite ids come from a per-graphics-mode table at
 * DS:0x020E, row stride DS:0x0208 words, row DS:0x4F86.
 *
 * @name draw_status_bar
 */


extern int D_4F86;              /* graphics-mode table index */
extern int D_0208;              /* row stride of the sprite table (words) */
extern int D_020E[];
extern int D_0210[];
extern int D_0212[];
extern int D_0216[];
extern int D_56EE;              /* g_lives */

void F_1BD6(int x, int y, int sprite);

void F_376E(void)
{
    int i;
    int row;

    row = D_4F86 * D_0208;
    F_1BD6(0, 0, D_0212[row]);
    F_1BD6(0x78, 0, D_0210[row]);
    F_1BD6(0xc8, 0, D_020E[row]);
    for (i = 0; i < D_56EE; i++)
        F_1BD6(i * 16 + 0x100, 0, D_0216[row]);
}
