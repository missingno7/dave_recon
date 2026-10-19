/*
 * @behaviour: In Turbo C++ 1.00, -Z (register load suppression) does nothing
 *   on its own: with -Z alone these functions compile identically. Only
 *   -O -Z drops the second `les bx,[fp]` / `mov bx,[np]` reload. The
 *   original keeps such reloads (see orig_F47F8_structarray: the index
 *   multiply is recomputed per access) and `jmp $+2`, so neither -O nor -Z
 *   is in effect. Note also: storing a global and reading it back
 *   (`a = b; c = b;`) always reloads, even with -O -Z.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. c4 1e .. ..
 *   26 c7 07 01 00 c4 1e .. .. 26 c7 47 02 02 00 5d
 *   c3 55 8b ec 39 26 .. .. 72 03 e8 .. .. 8b 1e ..
 *   .. c7 07 00 00 8b 1e .. .. c7 47 02 00 00 8b 1e
 *   .. .. a1 .. .. 89 47 04 5d c3 55 8b ec 39 26 ..
 *   .. 72 03 e8 .. .. a1 .. .. a3 .. .. a1 .. .. a3
 *   .. .. 5d c3
 * @asm-contains: les bx, ptr [0]
 * @same-as: -Z
 * @contrast: -O -Z
 */
struct S { int x, y, z; };
struct S far *fp;
struct S *np;
int a, b, c;

void far_two(void)
{
    fp->x = 1;
    fp->y = 2;
}

void near_three(void)
{
    np->x = 0;
    np->y = 0;
    np->z = a;
}

void reload(void)
{
    a = b;
    c = b;
}
