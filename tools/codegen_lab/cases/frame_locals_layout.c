/*
 * @behaviour: Frame and local layout. Locals are allocated downward from BP
 *   in DECLARATION order (first declared = highest address, bp-1/bp-2...).
 *   Anything bigger than a char is placed at an even offset (a 1-byte hole is
 *   left after an odd char run); chars pack. The frame size is rounded up to
 *   even. 2 bytes of locals is `dec sp; dec sp` (4c 4c), more is
 *   `sub sp,N` (83 ec NN); a function with locals ends `mov sp,bp; pop bp`.
 *   Register candidates (int/pointer locals whose address is never taken)
 *   take no stack slot at all -- address-taken ones (&a here) stay in memory.
 *   Order: `int a; char b; long c; int d[3]; char e;` gives a=bp-2,
 *   b=bp-3, c=bp-8 (hole at bp-4), d=bp-0xe, e=bp-0xf, frame 0x10.
 * @expect-text:
 *   55 8b ec 83 ec 10 39 26 .. .. 72 03 e8 .. .. 8d
 *   46 fe 50 e8 .. .. 44 44 8d 46 fd 50 e8 .. .. 44
 *   44 8d 46 f8 50 e8 .. .. 44 44 8d 46 f2 50 e8 ..
 *   .. 44 44 8d 46 f1 50 e8 .. .. 44 44 8b e5 5d c3
 *   55 8b ec 4c 4c 39 26 .. .. 72 03 e8 .. .. 8d 46
 *   fe 50 e8 .. .. 44 44 8b e5 5d c3 55 8b ec 83 ec
 *   10 39 26 .. .. 72 03 e8 .. .. 8d 46 f0 50 e8 ..
 *   .. 44 44 8d 46 f3 50 e8 .. .. 44 44 8d 46 f4 50
 *   e8 .. .. 44 44 8d 46 f8 50 e8 .. .. 44 44 8d 46
 *   ff 50 e8 .. .. 44 44 8b e5 5d c3
 * @asm-contains: sub sp, 0x10
 *   lea ax, [bp - 2]
 *   lea ax, [bp - 3]
 *   lea ax, [bp - 8]
 *   lea ax, [bp - 0xe]
 *   lea ax, [bp - 0xf]
 *   dec sp
 */
void use(void *);
int gi;

void layout(void)
{
    int a;
    char b;
    long c;
    int d[3];
    char e;

    use(&a);
    use(&b);
    use(&c);
    use(d);
    use(&e);
}

void two_bytes(void)
{
    int a;

    use(&a);
}

void reversed(void)
{
    char e;
    int d[3];
    long c;
    char b;
    int a;

    use(&a);
    use(&b);
    use(&c);
    use(d);
    use(&e);
}
