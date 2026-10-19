/* @flags -G */
/* @seg _DATA 0x1044 */
#include <dos.h>

extern int D_130E;
void F_6EF1(int w, int h);
void F_7071(char *s);
int F_7005(void);
void F_6EB9(void);

void F_55BC(void)
{
    char c;

    F_6EF1(24, 5);
    F_7071("  Mouse Configuration   \n\r");
    F_7071("  -------------------   \n\r");
    F_7071("Choose the sensitivity  \n\r");
    F_7071("of the mouse, 1 being   \n\r");
    F_7071("slow, 9 being fast:");
    do {
        c = F_7005() % 256;
        if (c == 27)
            c = '5';
    } while (c < '1' || c > '9');
    D_130E = 15 - (c - '0');
    F_6EB9();
    _AX = 0;
    geninterrupt(0x33);
    _AX = 4;
    _CX = 320;
    _DX = 100;
    geninterrupt(0x33);
}
