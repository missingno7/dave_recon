/*
 * @behaviour: REAL FUNCTION F_1321 (file 0x1321..0x13ff). Far data in the
 *   small model: passing a `char far` array pushes `mov ax,SEG; push ax;
 *   mov ax,OFFSET; push ax` (the SEG word is an MZ-relocated paragraph in the
 *   EXE, e.g. b8 58 1d). Assigning it to a `huge` local is `mov [bp-4],OFF;
 *   mov [bp-2],SEG`; `p + 4` on a huge pointer calls N_PADD@ with DX:AX = p,
 *   CX:BX = 4L; `*(long huge *)p` is `les bx,[bp-4]; push es:[bx+2];
 *   push es:[bx]`. A long argument is pushed high word first. `x - 1` is
 *   `dec ax`. A function with locals ends `mov sp,bp; pop bp; ret`.
 * @original: 0x1321 0x13ff
 * @contrast: -O
 */
extern int g_8b32, g_4f86;
extern long g_56f0;
extern char far ega_tiles[];
extern char far cga_tiles[];
extern char far vga_tiles[];
extern char far blob_c42[];
extern char far blob_11ef[];
extern char g_d5e[];
void f_5e99(char far *, int);
void f_7c00(char huge *, long, long);
void f_68de(char *, long);

void f1321(void)
{
    char huge *p;

    switch (g_8b32) {
    case 1:
        f_5e99(ega_tiles, 0);
        p = (char huge *)blob_c42;
        f_7c00(p + 4, g_56f0, *(long huge *)p);
        break;
    case 2:
        f_5e99(cga_tiles, 0);
        f_68de(g_d5e, g_56f0);
        break;
    case 3:
        f_5e99(vga_tiles, 0);
        p = (char huge *)blob_11ef;
        f_7c00(p + 4, g_56f0, *(long huge *)p);
        break;
    }
    g_4f86 = g_8b32 - 1;
}
