/* @flags -G */
#include <bios.h>

extern int D_8A12, D_8A14;
void F_7878(int x, int y, int c);
void F_7831(void);

int F_7005(void)
{
    register int i, key;

    do {
        i = 9;
        while ((key = bioskey(1)) == 0 && i < 13) {
            F_7878(D_8A12, D_8A14, i++);
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_7831();
        }
    } while (key == 0);
    F_7878(D_8A12, D_8A14, ' ');
    return bioskey(0);
}
