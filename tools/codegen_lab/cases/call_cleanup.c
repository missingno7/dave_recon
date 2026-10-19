/*
 * @behaviour: Calls (cdecl, near, small model): arguments pushed right to
 *   left, call is e8 rel16 (fixup), caller pops: 0 bytes nothing, 2 bytes
 *   `inc sp; inc sp` (44 44), 4+ bytes `add sp,N` (83 c4 NN). A long
 *   argument is pushed high word first. A char argument to a prototyped
 *   char parameter is `mov al,[c]; push ax` -- NOT widened (AH is junk).
 *   Constants: 0 is `xor ax,ax; push ax`, others `mov ax,imm; push ax`. Without -G the 2-byte cleanup is `pop cx` and
 *   4 bytes `pop cx; pop cx`.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. e8 .. .. 33
 *   c0 50 e8 .. .. 44 44 b8 05 00 50 e8 .. .. 44 44
 *   b8 02 00 50 b8 01 00 50 e8 .. .. 83 c4 04 ff 36
 *   .. .. ff 36 .. .. e8 .. .. 83 c4 04 a0 .. .. 50
 *   e8 .. .. 44 44 b8 03 00 50 b8 02 00 50 b8 01 00
 *   50 e8 .. .. 83 c4 06 5d c3
 * @asm-contains: inc sp
 *   add sp, 4
 *   add sp, 6
 *   xor ax, ax
 *   mov al, byte ptr [0]
 * @contrast: -G-
 */
void f0(void);
void f1(int);
void f2(int, int);
void fl(long);
void fc(char);
void f3(int, int, int);
char c;
long l;

void calls(void)
{
    f0();
    f1(0);
    f1(5);
    f2(1, 2);
    fl(l);
    fc(c);
    f3(1, 2, 3);
}
