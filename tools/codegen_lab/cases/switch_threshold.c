/*
 * @behaviour: Jump-table density threshold, measured by sweeping n = 4..7
 *   cases {0..n-2, top}: a table is used while range = top+1 <= 3*n+1
 *   (n=4: <=13, n=5: <=16, n=6: <=19, n=7: <=22); one more makes it a
 *   compare tree. 3 cases are never a table, whatever the range.
 *   t4_13 below is a table (cs: jmp), t4_14 is a compare tree.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. 8b 5e 04 83
 *   fb 0c 77 27 d1 e3 2e ff a7 .. .. c7 06 .. .. 01
 *   00 eb 20 c7 06 .. .. 02 00 eb 18 c7 06 .. .. 03
 *   00 eb 10 c7 06 .. .. 04 00 eb 08 c7 06 .. .. 63
 *   00 eb 00 5d c3 .. .. .. .. .. .. .. .. .. .. ..
 *   .. .. .. .. .. .. .. .. .. .. .. .. .. .. .. 55
 *   8b ec 39 26 .. .. 72 03 e8 .. .. 8b 46 04 3d 02
 *   00 74 24 7f 0b 0b c0 74 0e 3d 01 00 74 11 eb 27
 *   3d 0d 00 74 1a eb 20 c7 06 .. .. 01 00 eb 20 c7
 *   06 .. .. 02 00 eb 18 c7 06 .. .. 03 00 eb 10 c7
 *   06 .. .. 04 00 eb 08 c7 06 .. .. 63 00 eb 00 5d
 *   c3
 * @asm-contains: cmp bx, 0xc
 *   cmp ax, 0xd
 */
int g;

void t4_13(int x)
{
    switch (x) {
    case 0: g = 1; break;
    case 1: g = 2; break;
    case 2: g = 3; break;
    case 12: g = 4; break;
    default: g = 99; break;
    }
}

void t4_14(int x)
{
    switch (x) {
    case 0: g = 1; break;
    case 1: g = 2; break;
    case 2: g = 3; break;
    case 13: g = 4; break;
    default: g = 99; break;
    }
}
