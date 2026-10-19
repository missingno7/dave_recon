/*
 * F_6DC2 -- draw_text_window
 * cs [0x6bc2,0x6cb9) / file [0x6dc2,0x6eb9), 247 bytes. Strict match: tools/match_function.py.
 *
 * Draws a framed text window with frame characters 1..8 via F_7878, clears
 * its interior, stores the window rectangle (D_8A24/26/28/2A) and puts the
 * text cursor at its top-left inner cell (D_8A12/D_8A22, D_8A14).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name draw_text_window
 */

extern int D_8A24, D_8A26, D_8A28, D_8A2A;
extern int D_8A12, D_8A14, D_8A22;
void F_7878(int x, int y, int c);

void F_6DC2(int x1, int y1, int x2, int y2)
{
    register int x, y;

    D_8A24 = x1;
    D_8A28 = y1;
    D_8A26 = x2;
    D_8A2A = y2;
    F_7878(x1, y1, 1);
    for (x = x1 + 1; x < x2; x++)
        F_7878(x, y1, 2);
    F_7878(x2, y1, 3);
    for (y = y1 + 1; y < y2; y++) {
        F_7878(x1, y, 4);
        for (x = x1 + 1; x < x2; x++)
            F_7878(x, y, ' ');
        F_7878(x2, y, 5);
    }
    F_7878(x1, y2, 6);
    for (x = x1 + 1; x < x2; x++)
        F_7878(x, y2, 7);
    F_7878(x2, y2, 8);
    D_8A12 = D_8A22 = x1 + 1;
    D_8A14 = y1 + 1;
}
