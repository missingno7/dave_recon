/* @flags -G */
#include <dos.h>

extern int D_9EC0;
extern int D_654C, D_654E, D_6550, D_6552, D_6556;
extern int D_65B0[], D_65C4[];
void F_664B(int stick, int *px, int *py);

void F_59EC(void)
{
    int x, y;
    void interrupt (far *v)();

    D_654C = 0;
    D_654E = 0;
    if (D_9EC0 == 3 || D_9EC0 == 5)
        D_654C = 1;
    if (D_9EC0 == 5 || D_9EC0 == 4)
        D_654E = 1;
    D_65B0[0] = 1;
    D_65B0[1] = D_654C;
    D_65B0[2] = D_654E;
    D_65B0[3] = 0;
    D_65B0[4] = 0;
    D_65B0[5] = 1;
    D_65B0[6] = 1;
    D_65B0[7] = 0;
    D_65B0[8] = 0;
    D_65B0[9] = 0;
    D_6550 = 0;
    D_6552 = 0;
    F_664B(1, &x, &y);
    if (x < 500)
        D_6550 = 1;
    F_664B(2, &x, &y);
    if (x < 500)
        D_6550 = 2;
    D_6556 = 1;
    v = getvect(0x33);
    if (v == 0)
        D_6556 = 0;
    else if ((*(int far *)v & 0xff) == 0xcf)
        D_6556 = 0;
    D_65C4[0] = 1;
    D_65C4[1] = D_6556;
    D_65C4[2] = D_6550;
    D_65C4[3] = D_6552;
    D_65C4[4] = 0;
}
