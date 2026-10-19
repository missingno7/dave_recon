/*
 * @behaviour: long arithmetic. + and - are inline add/adc, sub/sbb on DX:AX;
 *   comparisons compare the high words first (signed jl/jg or unsigned
 *   jb/ja) and then the low words (always unsigned jb/ja/jbe). * calls
 *   LXMUL@ (DX:AX * CX:BX), / and % call LDIV@/LMOD@ (signed) or
 *   LUDIV@/LUMOD@ (unsigned) with both operands pushed (high word first),
 *   << and >> by a variable or constant call LXLSH@/LXRSH@ (LXURSH@ for
 *   unsigned) with the count in CL. A long constant is loaded as
 *   `mov dx,hi; mov ax,lo` (xor for zero halves).
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. a1 .. .. 8b
 *   16 .. .. 03 16 .. .. 13 06 .. .. 89 16 .. .. a3
 *   .. .. a1 .. .. 8b 16 .. .. 2b 16 .. .. 1b 06 ..
 *   .. 89 16 .. .. a3 .. .. 8b 0e .. .. 8b 1e .. ..
 *   8b 16 .. .. a1 .. .. e8 .. .. a3 .. .. 89 16 ..
 *   .. ff 36 .. .. ff 36 .. .. ff 36 .. .. ff 36 ..
 *   .. e8 .. .. a3 .. .. 89 16 .. .. ff 36 .. .. ff
 *   36 .. .. ff 36 .. .. ff 36 .. .. e8 .. .. a3 ..
 *   .. 89 16 .. .. 8b 16 .. .. a1 .. .. b1 04 e8 ..
 *   .. a3 .. .. 89 16 .. .. 8b 16 .. .. a1 .. .. 8a
 *   0e .. .. e8 .. .. a3 .. .. 89 16 .. .. 5d c3 55
 *   8b ec 39 26 .. .. 72 03 e8 .. .. a1 .. .. 8b 16
 *   .. .. 3b 06 .. .. 7f 0d 7c 06 3b 16 .. .. 73 05
 *   b8 01 00 eb 32 a1 .. .. 8b 16 .. .. 3b 06 .. ..
 *   72 0d 77 06 3b 16 .. .. 76 05 b8 02 00 eb 18 83
 *   3e .. .. 01 75 0d 81 3e .. .. a0 86 75 05 b8 03
 *   00 eb 04 33 c0 eb 00 5d c3
 * @asm-contains: adc
 *   sbb
 *   LXMUL@
 *   LDIV@
 *   LUMOD@
 *   LXLSH@
 */
long a, b;
unsigned long ua, ub;
int n;

void ops(void)
{
    a = a + b;
    a = a - b;
    a = a * b;
    a = a / b;
    ua = ua % ub;
    a = a << 4;
    a = a >> n;
}

int lcmp(void)
{
    if (a < b)
        return 1;
    if (ua > ub)
        return 2;
    if (a == 100000L)
        return 3;
    return 0;
}
