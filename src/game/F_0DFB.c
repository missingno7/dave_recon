/*
 * F_0DFB -- draw_level_number
 * cs [0x0bfb,0x0c57) / file [0xdfb,0xe57), 92 bytes.
 *
 * Draws the 1-based level number (D_56F4 + 1) as two digit tiles at
 * x = 0xB0 and 0xB8 using the per-mode digit base D_01EA.
 * @name draw_level_number -- evidence: /10 and %10 of g_current_level+1.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */
/* @flags -G */
extern int D_4F86;
extern int D_56F4;
extern int D_01EA[];
void F_1B84(int, int, int);

void F_0DFB(void)
{
    F_1B84(0xb0, 1, D_01EA[D_4F86] + (D_56F4 + 1) / 10);
    F_1B84(0xb8, 1, D_01EA[D_4F86] + (D_56F4 + 1) % 10);
}
