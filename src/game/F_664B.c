/*
 * F_664B -- read_joystick_axes
 * cs [0x644b,0x64f2) / file [0x664b,0x66f2), 167 bytes. Strict match: tools/match_function.py.
 *
 * Reads the game-port (201h) timing of joystick 1 (bits 0/1) or 2 (bits
 * 2/3): triggers the one-shots, then counts with interrupts disabled until
 * both axis bits drop or a count reaches 500.
 *
 * Evidence for the name: port 0x201, cli/sti, limit 500 shared with
 * detect_hardware.
 *
 * Codegen: `(v & mask) != 0` -> test/je/mov ax,1/xor ax,ax.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name read_joystick_axes
 */

#include <dos.h>

void F_664B(int stick, register int *px, register int *py)
{
    int v, xbit, ybit, xmask, ymask;

    if (stick == 1) {
        xmask = 1;
        ymask = 2;
    } else {
        xmask = 4;
        ymask = 8;
    }
    *px = 0;
    *py = 0;
    outportb(0x201, inportb(0x201));
    disable();
    do {
        v = inportb(0x201);
        xbit = (v & xmask) != 0;
        ybit = (v & ymask) != 0;
        *px += xbit;
        *py += ybit;
    } while (xbit + ybit && *px < 500 && *py < 500);
    enable();
}
