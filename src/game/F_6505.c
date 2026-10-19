/* @flags -G */
#include <dos.h>

struct input {
    int dir;
    int fire;
    int jump;
};

extern int D_130E;

struct input F_6505(void)
{
    int dx, dy;
    struct input in;
    register int x, y;

    dx = 0;
    dy = 0;
    _AX = 3;
    geninterrupt(0x33);
    x = _CX;
    y = _DX;
    in.fire = _BX & 1;
    in.jump = (_BX & 2) >> 1;
    if ((x - 320) / 2 > D_130E) {
        dx = 1;
        x = x - D_130E * 2;
    } else if ((x - 320) / 2 < -D_130E) {
        dx = -1;
        x = x + D_130E * 2;
    }
    if (y - 100 > D_130E) {
        dy = 1;
        y = y - D_130E;
    } else if (y - 100 < -D_130E) {
        dy = -1;
        y = y + D_130E;
    }
    _AX = 4;
    _CX = x;
    _DX = y;
    geninterrupt(0x33);
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
    return in;
}
