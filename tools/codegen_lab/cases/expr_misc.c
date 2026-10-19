/*
 * @behaviour: Assorted expression forms. ++/--/+=/-= on memory operate in
 *   place (inc/dec/add/sub word ptr [g]). x*2, x*4 and x<<1..3 are
 *   repeated `shl ax,1`; by 16 (<< 4 and up) `mov cl,4; shl ax,cl`; other
 *   constants `mov dx,K; imul dx`. Signed `/ 2` is still `cwd; idiv` but
 *   `>> 1` is `sar ax,1`; unsigned `/ 2` IS strength-reduced to `shr ax,1`.
 *   `-x` neg, `~x` not. A boolean value (`a || b`, `a && b`, `x == 3`) is
 *   `mov ax,1; jmp; xor ax,ax`; `!x` is `neg ax; sbb ax,ax; inc ax`; `?:`
 *   is two movs and a jmp. Struct assignment calls SCOPY@ (far src/dst
 *   pushed, CX = size). `if (c) break;` / `continue;` is NOT a direct
 *   conditional jump: the condition is inverted around a `jmp` (74 02 eb ..).
 *   Conditional jumps are 8086 short jumps only: a far target becomes
 *   `jNcc +3; jmp near` (the original has 118 such pairs). do/while tests
 *   at the bottom; `while (n--)` copies n to AX before the dec. `x > 0` on a
 *   register is `or si,si; jle skip`. if/else-if chains end each arm with
 *   a jmp past the rest.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. ff 06 .. ..
 *   ff 0e .. .. 83 06 .. .. 02 83 2e .. .. 05 ff 06
 *   .. .. ff 06 .. .. 5d c3 55 8b ec 56 8b 76 04 39
 *   26 .. .. 72 03 e8 .. .. 8b c6 d1 e0 50 e8 .. ..
 *   44 44 8b c6 d1 e0 d1 e0 50 e8 .. .. 44 44 8b c6
 *   ba 03 00 f7 ea 50 e8 .. .. 44 44 8b c6 b1 04 d3
 *   e0 50 e8 .. .. 44 44 8b c6 d1 e0 d1 e0 d1 e0 50
 *   e8 .. .. 44 44 8b c6 bb 02 00 99 f7 fb 50 e8 ..
 *   .. 44 44 8b c6 d1 f8 50 e8 .. .. 44 44 a1 .. ..
 *   d1 e8 50 e8 .. .. 44 44 a1 .. .. b1 04 d3 e8 50
 *   e8 .. .. 44 44 8b c6 25 ff 00 50 e8 .. .. 44 44
 *   8b c6 f7 d8 50 e8 .. .. 44 44 8b c6 f7 d0 50 e8
 *   .. .. 44 44 5e 5d c3 55 8b ec 56 8b 76 04 39 26
 *   .. .. 72 03 e8 .. .. 0b f6 75 07 83 3e .. .. 00
 *   74 05 b8 01 00 eb 02 33 c0 a3 .. .. 0b f6 74 0c
 *   83 3e .. .. 00 74 05 b8 01 00 eb 02 33 c0 a3 ..
 *   .. 8b c6 f7 d8 1b c0 40 a3 .. .. 83 fe 03 75 05
 *   b8 01 00 eb 02 33 c0 a3 .. .. 0b f6 74 05 b8 07
 *   00 eb 03 b8 09 00 a3 .. .. 5e 5d c3 55 8b ec 39
 *   26 .. .. 72 03 e8 .. .. b8 .. .. 1e 50 b8 .. ..
 *   1e 50 b9 06 00 e8 .. .. 5d c3 55 8b ec 56 57 8b
 *   7e 04 39 26 .. .. 72 03 e8 .. .. 33 f6 56 e8 ..
 *   .. 44 44 46 3b f7 7c f5 eb 06 57 e8 .. .. 44 44
 *   8b c7 4f 0b c0 75 f3 83 3e .. .. 00 74 02 eb 14
 *   83 3e .. .. 00 74 02 eb 09 b8 01 00 50 e8 .. ..
 *   44 44 eb e3 5f 5e 5d c3 55 8b ec 56 8b 76 04 39
 *   26 .. .. 72 03 e8 .. .. 83 fe 01 75 0b b8 01 00
 *   50 e8 .. .. 44 44 eb 19 83 fe 02 75 0b b8 02 00
 *   50 e8 .. .. 44 44 eb 09 b8 03 00 50 e8 .. .. 44
 *   44 0b f6 7e 0e 83 fe 0a 7d 09 b8 04 00 50 e8 ..
 *   .. 44 44 0b f6 7c 05 83 fe 0a 7e 09 b8 05 00 50
 *   e8 .. .. 44 44 5e 5d c3
 * @asm-contains: inc word ptr [0]
 *   add word ptr [0], 2
 *   mov cl, 4
 *   sar ax, 1
 *   shr ax, 1
 *   sbb ax, ax
 *   N_SCOPY@
 */
int g, h, arr[10];
unsigned ug;
struct Six { int a, b, c; } s1, s2;
void use(int);

void incdec(void)
{
    g++;
    g--;
    g += 2;
    g -= 5;
    arr[3]++;
    ++h;
}

void muls(int x)
{
    use(x * 2);
    use(x * 4);
    use(x * 3);
    use(x * 16);
    use(x << 3);
    use(x / 2);
    use(x >> 1);
    use(ug / 2);
    use(ug >> 4);
    use(x & 0xff);
    use(-x);
    use(~x);
}

void boolval(int x)
{
    g = (x || h);
    g = (x && h);
    g = !x;
    g = (x == 3);
    g = x ? 7 : 9;
}

void structs(void)
{
    s1 = s2;
}

void loops(int n)
{
    int i;
    i = 0;
    do {
        use(i);
        i++;
    } while (i < n);
    while (n--)
        use(n);
    for (;;) {
        if (g)
            break;
        if (h)
            continue;
        use(1);
    }
}

void ifelse(int x)
{
    if (x == 1)
        use(1);
    else if (x == 2)
        use(2);
    else
        use(3);
    if (x > 0 && x < 10)
        use(4);
    if (x < 0 || x > 10)
        use(5);
}
