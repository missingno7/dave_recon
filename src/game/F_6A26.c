/* @flags -G */
#include <bios.h>

extern int D_8A32[];

void F_6A26(void)
{
    register int i;

    while (bioskey(1))
        bioskey(0);
    for (i = 0; i < 128; i++)
        D_8A32[i] = 0;
}
