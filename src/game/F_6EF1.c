/*
 * F_6EF1 -- draw_centered_window
 * cs [0x6cf1,0x6d3b) / file [0x6ef1,0x6f3b), 74 bytes. Strict match: tools/match_function.py.
 *
 * Draws a w x h window centred on the 40x25 text screen.
 *
 * Codegen: `register int x, y;` - with equal weight the first-declared gets
 * DI.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name draw_centered_window
 */
/* @flags -G */
void F_6DC2(int x1, int y1, int x2, int y2);
void F_6EF1(int w, int h)
{
    register int x, y;
    x = 19 - w / 2;
    y = 11 - h / 2;
    F_6DC2(x, y, x + w + 2, y + h + 2);
}
