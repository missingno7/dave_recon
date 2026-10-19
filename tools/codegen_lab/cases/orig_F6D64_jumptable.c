/*
 * @behaviour: REAL FUNCTION F_6D64 dispatch head (file 0x6d64..0x6d8a, the
 *   range src/F_6D64.c proves). A 4-case dense switch (0..3) on a parameter
 *   is a jump table: `mov bx,[bp+4]; cmp bx,3; ja default; shl bx,1;
 *   jmp word ptr cs:[bx+TABLE]` (2e ff a7). In the original the 4-word table
 *   sits in _TEXT right after the function's `ret` (file 0x6dba). A near
 *   address converted to a far pointer is `mov [bp-4],OFF; mov [bp-2],ds`
 *   (8c 5e fe). The case bodies here are size-matched placeholders (the
 *   original uses inline asm int 10h, which needs TASM).
 * @original: 0x6d64 0x6d8a
 */
struct GameStuff { char data[4]; };
struct GameStuff huge_thing;

void f6d64(int which)
{
    struct GameStuff far *p = (struct GameStuff far *)&huge_thing;

    switch (which) {
    case 0: p->data[0] = 0; p->data[2] = 5; break;
    case 1: p->data[0] = 1; break;
    case 2: p->data[0] = 2; break;
    case 3: p->data[0] = 3; break;
    }
}
