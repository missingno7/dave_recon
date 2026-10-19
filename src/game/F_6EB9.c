/*
 * F_6EB9 -- clear_text_window
 * cs [0x6cb9,0x6cf1) / file [0x6eb9,0x6ef1), 56 bytes. Strict match: tools/match_function.py.
 *
 * Fills the stored window rectangle with spaces.
 *
 * Codegen: Register vars: the inner-loop variable gets SI (higher use
 * weight).
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name clear_text_window
 */
/* @flags -G */
extern int D_8A24, D_8A26, D_8A28, D_8A2A;
void F_7878(int x, int y, int c);

void F_6EB9(void)
{
    register int x, y;

    for (y = D_8A28; y <= D_8A2A; y++)
        for (x = D_8A24; x <= D_8A26; x++)
            F_7878(x, y, ' ');
}
