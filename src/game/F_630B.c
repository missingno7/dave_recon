/*
 * F_630B -- keyboard_isr (INT 9 handler)
 * cs [0x610b,0x6188) / file [0x630b,0x6388), 125 bytes. EXACT (strict).
 *
 * Reads the scan code from port 60h. A break code (> 0x7F) clears
 * key_down[key - 0x80]; a make code sets key_down[key] = 1 and empties the
 * BIOS keyboard buffer (0040:001C = 0040:001A). Then chains to the old INT 9
 * handler (D_131A, saved by F_6293) and acknowledges the PIC
 * (outport(0x20, 0x20)).
 *
 * @name keyboard_isr
 * Original inline asm: the explicit `push ax..bp` / `pop bp..ax` around the
 * chained call cannot come from C (TC emits only `pushf; call far [old]`).
 * It also explains why `key` lives at [bp-2] and not in SI: TC does no
 * register allocation in a function that contains `asm` statements.
 */
#include <dos.h>

extern int D_8A32[];
extern void interrupt (far *D_131A)();

void interrupt F_630B(void)
{
    int key;

    key = inportb(0x60);
    if (key > 0x7f)
        D_8A32[key - 0x80] = 0;
    else {
        D_8A32[key] = 1;
        poke(0x40, 0x1c, peek(0x40, 0x1a));
    }
    asm push ax
    asm push bx
    asm push cx
    asm push dx
    asm push si
    asm push di
    asm push bp
    (*D_131A)();
    asm pop bp
    asm pop di
    asm pop si
    asm pop dx
    asm pop cx
    asm pop bx
    asm pop ax
    outport(0x20, 0x20);
}
