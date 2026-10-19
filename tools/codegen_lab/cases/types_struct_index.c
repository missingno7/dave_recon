/*
 * @behaviour: Struct layout and indexing. No padding anywhere (no -a): a
 *   struct is the plain sum of its members, char fields can leave ints at
 *   odd offsets. Element size 2 indexes with `shl bx,1`, 4 with two
 *   `shl bx,1`, any other size with `mov ax,i; mov dx,SIZE; imul dx;
 *   mov bx,ax` (never repeated shifts/adds). A 2-D int array a[i][j] is
 *   i*ROWBYTES via imul then j*2 via shl, added. Field access folds the field
 *   offset into the displacement ([bx+ARRAY+FIELD]). sizeof is a constant.
 * @expect-text:
 *   55 8b ec 39 26 .. .. 72 03 e8 .. .. 8b 46 04 ba
 *   05 00 f7 ea 8b d8 8b 87 .. .. eb 00 5d c3 55 8b
 *   ec 39 26 .. .. 72 03 e8 .. .. 8b 5e 04 d1 e3 d1
 *   e3 8b 97 .. .. 8b 87 .. .. eb 00 5d c3 55 8b ec
 *   39 26 .. .. 72 03 e8 .. .. 8b 46 04 ba 28 00 f7
 *   ea 8b 56 06 d1 e2 03 c2 8b d8 8b 87 .. .. eb 00
 *   5d c3 55 8b ec 39 26 .. .. 72 03 e8 .. .. b8 05
 *   00 eb 00 5d c3
 * @asm-contains: mov dx, 5
 *   imul dx
 *   mov dx, 0x28
 *   shl bx, 1
 */
struct Odd { char tag; int val; int w; };   /* 5 bytes */
struct Odd odds[10];
long longs[10];
int grid[10][20];

int get_val(int i)
{
    return odds[i].val;
}

long get_long(int i)
{
    return longs[i];
}

int get_grid(int i, int j)
{
    return grid[i][j];
}

int size_odd(void)
{
    return sizeof(struct Odd);
}
