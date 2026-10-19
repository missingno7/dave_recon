/*
 * @behaviour: What -G does to register allocation: mentions inside loops get
 *   extra weight. Here b has 4 straight-line mentions and the loop counter a
 *   has 3 (init, test, increment): with -G the loop counter wins SI (xor si,si)
 *   and b gets DI; with -G- it is the other way round. A parameter used once
 *   inside a loop is auto-registered only under -G (mov di,[bp+4]).
 * @expect-text:
 *   55 8b ec 56 57 39 26 .. .. 72 03 e8 .. .. bf 22
 *   00 57 e8 .. .. 44 44 57 e8 .. .. 44 44 57 e8 ..
 *   .. 44 44 33 f6 eb 01 46 83 fe 0a 7c fa 5f 5e 5d
 *   c3 55 8b ec 56 57 8b 7e 04 39 26 .. .. 72 03 e8
 *   .. .. 33 f6 eb 07 57 e8 .. .. 44 44 46 83 fe 0a
 *   7c f4 ff 76 06 e8 .. .. 44 44 5f 5e 5d c3
 * @asm-contains: xor si, si
 *   mov di, 0x22
 *   mov di, word ptr [bp + 4]
 * @contrast: -G-
 */
void use(int);

void loop_vs_plain(void)
{
    int a, b;
    b = 0x22;
    use(b); use(b); use(b);
    for (a = 0; a < 10; a++)
        ;
}

void param_in_loop(int p, int q)
{
    int i;
    for (i = 0; i < 10; i++)
        use(p);
    use(q);
}
