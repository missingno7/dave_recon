/* @flags -G */
/* @seg _DATA 0x0d47 */
#include <bios.h>
extern int D_8A12;
extern int D_8A14;
extern int D_8B32;
void F_76BF(void);
void F_6EF1(int, int);
void F_7071(char *);
int F_7005(void);
void F_6D64(int);
void F_13FF(void);
void F_76E1(void);

void F_12B9(void)
{
    int i;
    int c;

    F_76BF();
    for (i = 2; i < 0x18; i += 2)
        F_6EF1(i, 2);
    D_8A12 = 9;
    D_8A14 = 0xc;
    F_7071("Press F9 to end pause:");
    bioskey(0);
    do {
        c = F_7005();
    } while ((c >> 8) != 0x43);
    F_6D64(D_8B32);
    F_13FF();
    F_76E1();
}
