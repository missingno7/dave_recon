/*
 * @behaviour: REAL FUNCTION F_2D38 (file 0x2d38..0x2d87). A plain `char`
 *   loaded for use as an index is sign-extended with cbw (8a 01 98): char is
 *   SIGNED (no -K). Two int locals are auto-allocated to registers (no
 *   `register` keyword needed): the first-assigned DI, the second SI. int
 *   division by a constant is `mov bx,16; cwd; idiv bx` (no shift
 *   strength-reduction). `return expr;` at the end of the function still
 *   jumps to the epilogue (eb 00).
 * @original: 0x2d38 0x2d87
 * @contrast: -K        # unsigned char: mov ah,0 instead of cbw
 *   -r-
 *   -p
 *   -O
 */
extern int g_57a0;
extern char *g_57a8;
extern int g_13dd[];
extern int g_2cc[];

int f2d38(int x, int y, int w, int h)
{
    int col, row;

    col = (w + x) / 16 + g_57a0;
    row = (y + h - 16) / 16;
    return g_2cc[(g_57a8 + g_13dd[row])[col]];
}
