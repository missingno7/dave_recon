/*
 * F_6293 -- install_keyboard_handler
 * cs [0x6093,0x610b) / file [0x6293,0x630b), 120 bytes. Strict match: tools/match_function.py.
 *
 * Reads the INT 9 vector, clears the key-state table D_8A32[128], flushes
 * the BIOS keyboard buffer (head = tail at 0040:001A/1C) and, unless the
 * handler is already ours, saves the old vector in D_131A and installs
 * F_630B.
 *
 * Evidence for the name: getvect/setvect(9); far pointer to F_630B uses MZ
 * relocations at load-module 0x60DC/0x60F5.
 *
 * Codegen: Comparing a far function pointer with F_630B gives cmp [bp-2],SEG
 * / cmp [bp-4],OFF.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name install_keyboard_handler
 */

#include <dos.h>

extern int D_8A32[];
extern void interrupt (far *D_131A)();
void interrupt F_630B();

void F_6293(void)
{
    void interrupt (far *v)();
    register int i;

    v = getvect(9);
    for (i = 0; i < 128; i++)
        D_8A32[i] = 0;
    poke(0x40, 0x1c, peek(0x40, 0x1a));
    if (v != F_630B) {
        D_131A = v;
        setvect(9, F_630B);
    }
}
