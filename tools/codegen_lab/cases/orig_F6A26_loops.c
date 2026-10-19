/*
 * @behaviour: REAL FUNCTION F_6A26 (file 0x6a26..0x6a62). `while (c) s;`
 *   is `jmp cond; body: s; cond: c; jne body` (test at the bottom, entered
 *   by a forward jmp). A call result tested for truth is `or ax,ax`.
 *   Storing to int g[i] is `mov bx,si; shl bx,1; mov word ptr [bx+g],0`.
 *   The loop counter is auto-registered into SI.
 * @original: 0x6a26 0x6a62
 * @contrast: -O
 *   -G-
 *   -r-
 */
int bioskey(int);
extern int g_8a32[];

void f6a26(void)
{
    int i;

    while (bioskey(1))
        bioskey(0);
    for (i = 0; i < 128; i++)
        g_8a32[i] = 0;
}
