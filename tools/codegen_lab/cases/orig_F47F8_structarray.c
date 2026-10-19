/*
 * @behaviour: REAL FUNCTION F_47F8 (file 0x47f8..0x483f). Indexing an array
 *   of 14-byte structs: `mov ax,si; mov dx,14; imul dx; mov bx,ax` then
 *   `[bx+OFFSET+field]`, recomputed for every access (no CSE). A `for` loop
 *   is init; jmp cond; body; inc; cond: cmp; jl body. `return i;` inside the
 *   loop and the final `return -1;` both jump to the shared epilogue.
 *   The int parameter used 2x inside the loop is auto-registered (DI) under
 *   -G, loaded before the stack check.
 * @original: 0x47f8 0x483f
 * @contrast: -O
 *   -r-
 */
struct Obj { int type; int a, b, c, d, e; int id; };
extern struct Obj g_56f6[];

int f47f8(int id)
{
    int i;

    for (i = 0; i < 5; i++) {
        if (g_56f6[i].type == 1 && g_56f6[i].id == id)
            return i;
    }
    return -1;
}
