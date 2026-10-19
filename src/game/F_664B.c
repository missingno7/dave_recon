/* @flags -G */
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
