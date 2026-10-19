/*
 * @behaviour: Register variable allocation (-r, default ON; -G changes the
 *   weights). Candidates: int/unsigned/near-pointer locals whose address is
 *   never taken (char and long never). No `register` keyword is needed.
 *   Priority: explicitly `register` variables first, then by use count
 *   (each mention counts; under -G mentions inside loops weigh more). The
 *   top one gets SI, the next DI, the rest stay on the stack. Ties go to
 *   the LATER declaration (it gets SI). Parameters are candidates too but
 *   only with >= 3 mentions (or loop-weighted under -G; a pointer param
 *   dereferenced twice qualifies); a register parameter is loaded
 *   (mov si,[bp+N]) before the -N stack check. SI/DI are saved with
 *   `push si; push di` after the frame and restored `pop di; pop si`.
 *   Init constants identify the variables: a=0x11 b=0x22 c=0x33.
 * @expect-text:
 *   55 8b ec 56 57 39 26 .. .. 72 03 e8 .. .. bf 11
 *   00 be 22 00 57 e8 .. .. 44 44 56 e8 .. .. 44 44
 *   5f 5e 5d c3 55 8b ec 4c 4c 56 57 39 26 .. .. 72
 *   03 e8 .. .. c7 46 fe 11 00 bf 22 00 be 33 00 ff
 *   76 fe e8 .. .. 44 44 57 e8 .. .. 44 44 56 e8 ..
 *   .. 44 44 5f 5e 8b e5 5d c3 55 8b ec 4c 4c 56 57
 *   39 26 .. .. 72 03 e8 .. .. be 11 00 c7 46 fe 22
 *   00 bf 33 00 56 e8 .. .. 44 44 56 e8 .. .. 44 44
 *   56 e8 .. .. 44 44 ff 76 fe e8 .. .. 44 44 57 e8
 *   .. .. 44 44 5f 5e 8b e5 5d c3 55 8b ec 4c 4c 56
 *   57 39 26 .. .. 72 03 e8 .. .. c7 46 fe 11 00 bf
 *   22 00 be 33 00 ff 76 fe e8 .. .. 44 44 ff 76 fe
 *   e8 .. .. 44 44 ff 76 fe e8 .. .. 44 44 57 e8 ..
 *   .. 44 44 57 e8 .. .. 44 44 57 e8 .. .. 44 44 56
 *   e8 .. .. 44 44 5f 5e 8b e5 5d c3 55 8b ec 56 8b
 *   76 04 39 26 .. .. 72 03 e8 .. .. 56 e8 .. .. 44
 *   44 56 e8 .. .. 44 44 56 e8 .. .. 44 44 ff 76 06
 *   e8 .. .. 44 44 5e 5d c3 55 8b ec 39 26 .. .. 72
 *   03 e8 .. .. ff 76 04 e8 .. .. 44 44 ff 76 04 e8
 *   .. .. 44 44 ff 76 06 e8 .. .. 44 44 5d c3 55 8b
 *   ec 4c 4c 56 39 26 .. .. 72 03 e8 .. .. c7 46 fe
 *   11 00 be 22 00 8d 46 fe 50 e8 .. .. 44 44 56 e8
 *   .. .. 44 44 5e 8b e5 5d c3
 * @asm-contains: mov di, 0x11
 *   mov si, 0x22
 *   mov word ptr [bp - 2], 0x11
 *   mov si, 0x33
 *   mov si, 0x11
 *   mov word ptr [bp - 2], 0x22
 *   mov si, word ptr [bp + 4]
 */
void use(int);

void tie_later_wins(void)       /* a=DI, b=SI */
{
    int a, b;
    a = 0x11; b = 0x22;
    use(a); use(b);
}

void three_tie(void)            /* a=[bp-2], b=DI, c=SI */
{
    int a, b, c;
    a = 0x11; b = 0x22; c = 0x33;
    use(a); use(b); use(c);
}

void count_wins(void)           /* a used most = SI, b stack, c = DI */
{
    int a, b, c;
    a = 0x11; b = 0x22; c = 0x33;
    use(a); use(a); use(a); use(b); use(c);
}

void keyword_first(void)        /* register c beats heavier a, b: c=SI, b=DI */
{
    int a, b;
    register int c;
    a = 0x11; b = 0x22; c = 0x33;
    use(a); use(a); use(a); use(b); use(b); use(b); use(c);
}

void param3(int p, int q)       /* p mentioned 3x -> SI */
{
    use(p); use(p); use(p);
    use(q);
}

void param2(int p, int q)       /* 2 mentions: stays [bp+4] */
{
    use(p); use(p);
    use(q);
}

void addr_taken(void)           /* &a: a on the stack, b = SI */
{
    void take(int *);
    int a, b;
    a = 0x11; b = 0x22;
    take(&a);
    use(b);
}
