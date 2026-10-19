/*
 * F_66F2 -- read_joystick_input
 * cs [0x64f2,0x668c) / file [0x66f2,0x688c), 410 bytes. Strict match: tools/match_function.py.
 *
 * Joystick input reader: axis counts compared with calibration limits
 * D_12F6/D_12FC (x) and D_1302/D_1308 (y) per stick, out-of-range readings
 * replaced by min+1, direction from the switch table, buttons from port 201h
 * bits (stick 1: 0x10/0x20, stick 2: 0x40/0x80, active low).
 *
 * Evidence for the name: calibration arrays indexed by stick, port 0x201.
 *
 * Codegen: `(x > 500) | (y > 500)` (bitwise or of two comparisons) gives
 * push/pop dx/or dx,ax.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name read_joystick_input
 */
/* @flags -G */
#include <dos.h>

struct input {
    int dir;
    int fire;
    int jump;
};

extern int D_12F6[], D_12FC[], D_1302[], D_1308[];
void F_664B(int stick, int *px, int *py);

struct input F_66F2(register int stick)
{
    int x, y, dx, dy;
    struct input in;
    register int b;

    x = 0;
    y = 0;
    dx = 0;
    dy = 0;
    F_664B(stick, &x, &y);
    if ((x > 500) | (y > 500)) {
        x = D_12F6[stick] + 1;
        y = D_1302[stick] + 1;
    }
    if (D_12FC[stick] < x)
        dx = 1;
    else if (D_12F6[stick] > x)
        dx = -1;
    if (D_1308[stick] < y)
        dy = 1;
    else if (D_1302[stick] > y)
        dy = -1;
    switch (dy * 3 + dx) {
    case -4: in.dir = 7; break;
    case -3: in.dir = 0; break;
    case -2: in.dir = 1; break;
    case -1: in.dir = 6; break;
    case 0: in.dir = 8; break;
    case 1: in.dir = 2; break;
    case 2: in.dir = 5; break;
    case 3: in.dir = 4; break;
    case 4: in.dir = 3; break;
    }
    b = inportb(0x201);
    if (stick == 1) {
        in.fire = (b & 0x10) == 0;
        in.jump = (b & 0x20) == 0;
    } else {
        in.fire = (b & 0x40) == 0;
        in.jump = (b & 0x80) == 0;
    }
    return in;
}
