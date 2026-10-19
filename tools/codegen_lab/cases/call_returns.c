/*
 * @behaviour: Return values: int/pointer in AX, char in AL (callers widen),
 *   long in DX:AX (high in DX). Every `return expr;` loads AX then jumps to
 *   the epilogue -- even when the epilogue is the next instruction (eb 00).
 *   A void function that falls off its end has no jmp. A function that
 *   assigns a callee's return to a long stores AX then DX.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. 8b 46 04 ba
 *   03 00 f7 ea eb 00 5d c3 55 8b ec 39 26 .. .. 72
 *   03 e8 .. .. 8b 5e 04 8a 47 01 eb 00 5d c3 55 8b
 *   ec 39 26 .. .. 72 03 e8 .. .. 8b 16 .. .. a1 ..
 *   .. 05 01 00 83 d2 00 eb 00 5d c3 55 8b ec 39 26
 *   .. .. 72 03 e8 .. .. 83 7e 04 00 7d 04 33 c0 eb
 *   0b 8b 46 04 a3 .. .. b8 01 00 eb 00 5d c3 55 8b
 *   ec 39 26 .. .. 72 03 e8 .. .. e8 .. .. a3 .. ..
 *   89 16 .. .. 5d c3
 * @asm-contains: jmp 0x
 * @contrast: -O
 */
long lg;
int ig;
long getl(void);

int ret_int(int x)
{
    return x * 3;
}

char ret_char(char *p)
{
    return p[1];
}

long ret_long(void)
{
    return lg + 1;
}

int early(int x)
{
    if (x < 0)
        return 0;
    ig = x;
    return 1;
}

void store_long(void)
{
    lg = getl();
}
