/*
 * @behaviour: REAL FUNCTION F_1B84 (file 0x1b84..0x1bd6). `register`
 *   parameters are copied into DI/SI right after `push si; push di` and
 *   BEFORE the -N stack check (8b 7e 06 / 8b 76 08 precede 39 26). Here the
 *   2nd parameter gets DI and the 3rd SI (equal use counts: the later
 *   declared register variable wins SI). Arguments are pushed right to left
 *   and a 6-byte cleanup is `add sp,6` (83 c4 06).
 * @original: 0x1b84 0x1bd6
 * @contrast: -r-       # register variables off: parameters stay on the stack
 *   -O
 */
extern int g_4f86;
void a(int, int, int); void b(int, int, int); void c(int, int, int);

void f1b84(int p, register int q, register int r)
{
    switch (g_4f86) {
    case 0: a(p, q, r); break;
    case 1: b(p, q, r); break;
    case 2: c(p, q, r); break;
    }
}
