/*
 * @behaviour: Signedness and promotions. Plain char is signed: char to int
 *   is `mov al,..; cbw`, char compares use signed jumps and compare the
 *   byte in memory directly (`cmp byte ptr [x],imm`). `if (cond) stmt`
 *   branches on the INVERTED condition around stmt: `if (c < 0x20)` is
 *   `cmp byte ptr [c],0x20; jge skip`. unsigned char widens with
 *   `mov ah,0`; unsigned int compares use jb/ja/jbe/jae (`if (a < u)` is
 *   `jae skip`). int to char is a plain byte store of AL. int to long is
 *   cwd; unsigned to long stores the low word and `mov word ptr [hi],0`.
 *   Comparing a memory int with 0 is `cmp word ptr [x],0`.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. a0 .. .. 98
 *   a3 .. .. a0 .. .. b4 00 a3 .. .. a0 .. .. a2 ..
 *   .. a1 .. .. 99 a3 .. .. 89 16 .. .. a1 .. .. a3
 *   .. .. c7 06 .. .. 00 00 5d c3 55 8b ec 39 26 ..
 *   .. 72 03 e8 .. .. 80 3e .. .. 20 7d 05 b8 01 00
 *   eb 10 80 3e .. .. 5a 7e 05 b8 02 00 eb 04 33 c0
 *   eb 00 5d c3 55 8b ec 39 26 .. .. 72 03 e8 .. ..
 *   8b 46 04 3b 06 .. .. 73 05 b8 01 00 eb 10 83 3e
 *   .. .. 00 7d 05 b8 02 00 eb 04 33 c0 eb 00 5d c3
 * @asm-contains: cwde
 *   mov ah, 0
 *   jge 0x
 *   jae 0x
 *   cmp byte ptr
 *   cdq
 *   mov word ptr [6], 0
 * @contrast: -K
 */
char c;
unsigned char uc;
int i;
unsigned u;
long l;

void widen(void)
{
    i = c;
    i = uc;
    c = i;
    l = i;
    l = u;
}

int cmp_char(void)
{
    if (c < 0x20)
        return 1;
    if (c > 'Z')
        return 2;
    return 0;
}

int cmp_unsigned(unsigned a)
{
    if (a < u)
        return 1;
    if (i < 0)
        return 2;
    return 0;
}
