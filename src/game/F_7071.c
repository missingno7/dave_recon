/*
 * F_7071 -- print_string
 * cs [0x6e71,0x6ecb) / file [0x7071,0x70cb), 90 bytes. Strict match: tools/match_function.py.
 *
 * Prints a string at the text cursor handling \n (next line, column reset to
 * D_8A22) and \r.
 *
 * Codegen: `char c` is not register-allocated.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name print_string
 */
/* @flags -G */
extern int D_8A12, D_8A14, D_8A22;
void F_7878(int x, int y, int c);

void F_7071(char *s)
{
    char c;

    while ((c = *s++) != 0) {
        if (c == '\n') {
            D_8A14++;
            D_8A12 = D_8A22;
        } else if (c == '\r')
            D_8A12 = D_8A22;
        else
            F_7878(D_8A12++, D_8A14, c);
    }
}
