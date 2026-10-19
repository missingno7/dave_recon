/*
 * F_124B -- ask_quit
 * cs [0x104b,0x10b9) / file [0x124b,0x12b9), 110 bytes.
 *
 * F10/ESC handler: "Quit? (Y or N):"; N redraws (F_13FF), Y exits via
 * quit_game(0); then F_76E1.
 * @name ask_quit -- evidence: the prompt string.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */
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
