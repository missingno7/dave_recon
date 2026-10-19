/*
 * F_6388 -- restore_keyboard_handler
 * cs [0x6188,0x61af) / file [0x6388,0x63af), 39 bytes. Strict match: tools/match_function.py.
 *
 * Restores the saved INT 9 vector D_131A.
 *
 * Evidence for the name: setvect(9, D_131A).
 *
 * Codegen: The original tests the ADDRESS of D_131A (mov ax,0x131a / or
 * ax,ax), reproduced as `if (&D_131A)`.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name restore_keyboard_handler
 */

#include <dos.h>

extern void interrupt (far *D_131A)();

void F_6388(void)
{
    if (&D_131A)
        setvect(9, D_131A);
}
