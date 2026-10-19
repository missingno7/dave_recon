/* @flags -G */
/* @seg _DATA 0x131e */
#include <stdio.h>
#include <dos.h>
#include <alloc.h>

extern void far *D_9EC4;
void F_6D64(int mode);
void F_04D2(int code);

void far *F_6A62(unsigned long size)
{
    void huge *p;
    register unsigned seg, off;

    D_9EC4 = p = farmalloc(size + 15);
    if (p == NULL) {
        F_6D64(0);
        puts("Out of memory!");
        F_04D2(1);
    }
    off = FP_OFF(p);
    if (off) {
        seg = FP_SEG(p);
        seg++;
        off = 0;
        p = MK_FP(seg, off);
    }
    return p;
}

