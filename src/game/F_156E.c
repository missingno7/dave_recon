/* @flags -G */
#include <dos.h>
#include <mem.h>
#include <bios.h>

void F_156E(void)
{
    char far *p;

    _AX = 4; geninterrupt(0x10);
    movedata(FP_SEG(p), FP_OFF(p), 0xb800, 0, 0x4000);
    bioskey(0);
}
