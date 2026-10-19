/*
 * @behaviour: REAL FUNCTION F_1C28 (file 0x1c28..0x1c6a). A 3-case switch
 *   (0,1,2) on a global: `mov ax,[g]; or ax,ax; je c0; cmp ax,1; je c1;
 *   cmp ax,2; je c2; jmp end` -- case 0 is tested with `or ax,ax`, not cmp.
 *   The address of a near global array as an argument is `mov ax,OFFSET;
 *   push ax` (b8 .. ..). Every case's `break` is a jmp, the last one eb 00.
 * @original: 0x1c28 0x1c6a
 * @contrast: -O
 *   -G-
 */
extern int g_4f86;
extern char g_4c64[];
void a(char *); void b(char *); void c(char *);

void f1c28(void)
{
    switch (g_4f86) {
    case 0: a(g_4c64); break;
    case 1: b(g_4c64); break;
    case 2: c(g_4c64); break;
    }
}
