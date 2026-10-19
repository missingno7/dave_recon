/*
 * @behaviour: No -a (word alignment). struct { char name[3]; long score; }
 *   is 7 bytes, so indexing an array of them is `mov ax,i; mov dx,7;
 *   imul dx`. With -a the long is padded to offset 4 and the stride is 8.
 *   ORIGINAL EVIDENCE: F_04FC (file 0x55b..0x564) indexes its table with
 *   8b c6 ba 07 00 f7 ea 8b d8 8b 87 b9 57 (mov ax,si; mov dx,7; imul dx;
 *   mov bx,ax; mov ax,[bx+0x57b9]) -- a 7-byte stride.
 * @asm-contains: mov dx, 7
 *   imul dx
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. 8b 46 04 ba
 *   07 00 f7 ea 8b d8 8b 97 .. .. 8b 87 .. .. eb 00
 *   5d c3
 * @contrast: -a
 */
struct Score { char name[3]; long score; };
struct Score table[8];

long get(int i)
{
    return table[i].score;
}
