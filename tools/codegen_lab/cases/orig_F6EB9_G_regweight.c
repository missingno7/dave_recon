/*
 * @behaviour: REAL FUNCTION F_6EB9 (file 0x6eb9..0x6ef1). Decisive -G
 *   evidence beyond call cleanup: with -G the register allocator weights
 *   uses inside loops, so the INNER loop variable x (declared first) gets SI
 *   and the outer y gets DI (8b 3e = mov di,[g_8a28] first). Without -G the
 *   last-declared variable gets SI and the registers swap.
 * @original: 0x6eb9 0x6ef1
 * @contrast: -G-
 *   -r-
 */
extern int g_8a24, g_8a26, g_8a28, g_8a2a;
void put(int, int, int);

void f6eb9(void)
{
    int x, y;

    for (y = g_8a28; y <= g_8a2a; y++)
        for (x = g_8a24; x <= g_8a26; x++)
            put(x, y, 0x20);
}
