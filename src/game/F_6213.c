/* @flags -G */
#include <dos.h>
#include <mem.h>

extern unsigned D_65A8[];
extern unsigned D_65AA;

void F_6213(void)
{
    int i;

    for (i = 0; i < 4; i++) {
        outportb(0x3c4, 2);
        outportb(0x3c5, 1 << i);
        movedata(D_65A8[i], 0, 0xa200, 0, (D_65AA - D_65A8[0]) << 4);
    }
    outportb(0x3c4, 2);
    outportb(0x3c5, 0xf);
}
