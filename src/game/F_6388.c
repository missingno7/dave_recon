/* @flags -G */
#include <dos.h>

extern void interrupt (far *D_131A)();

void F_6388(void)
{
    if (&D_131A)
        setvect(9, D_131A);
}
