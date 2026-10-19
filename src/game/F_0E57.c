/*
 * F_0E57 -- ask_restart
 * cs [0x0c57,0x0cdf) / file [0xe57,0xedf), 136 bytes.
 *
 * F3 handler: opens a text window, prints "Restart Game? (Y or N):",
 * waits for Y/N. On Y (and not already on the title, D_00AA != 3) it
 * restores the level tiles (movmem D_615C <- D_57A8, 1000 bytes), sets the
 * title state and calls F_769B; otherwise it redraws (F_13FF, F_76E1).
 * @name ask_restart -- evidence: the prompt string.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 * single literal: _DATA placed at the literal (0x090B).
 */
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
