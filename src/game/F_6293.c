/* @flags -G */
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
