/* @flags -G */
/* @seg _DATA 0x0d37 */
#include <ctype.h>
extern int D_8A12;
extern int D_8A14;
void F_76BF(void);
void F_6EF1(int, int);
void F_7071(char *);
int F_7005(void);
void F_13FF(void);
void F_04D2(int);
void F_76E1(void);

void F_124B(void)
{
    int i;
    int c;

    F_76BF();
    for (i = 2; i < 0x13; i += 2)
        F_6EF1(i, 2);
    D_8A12 = 0xc;
    D_8A14 = 0xc;
    F_7071("Quit? (Y or N):");
    do {
        c = toupper(F_7005() & 0xff);
    } while (c != 'N' && c != 'Y');
    if (c == 'N')
        F_13FF();
    else
        F_04D2(0);
    F_76E1();
}
