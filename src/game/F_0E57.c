/* @flags -G */
/* @seg _DATA 0x090b */
#include <ctype.h>
#include <mem.h>
extern int D_8A12;
extern int D_8A14;
extern int D_00AA;
extern char *D_57A8;
extern char D_615C[];
void F_76BF(void);
void F_6EF1(int, int);
void F_7071(char *);
int F_7005(void);
void F_769B(void);
void F_13FF(void);
void F_76E1(void);

void F_0E57(void)
{
    int i;
    int c;

    F_76BF();
    for (i = 2; i < 0x19; i += 2)
        F_6EF1(i, 2);
    D_8A12 = 8;
    D_8A14 = 0xc;
    F_7071("Restart Game? (Y or N):");
    do {
        c = toupper(F_7005() & 0xff);
    } while (c != 'N' && c != 'Y');
    if (c == 'Y' && D_00AA != 3) {
        movmem(D_615C, D_57A8, 1000);
        D_00AA = 3;
        F_769B();
    } else {
        F_13FF();
        F_76E1();
    }
}
