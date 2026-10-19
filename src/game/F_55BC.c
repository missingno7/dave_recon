/*
 * F_55BC -- config_mouse
 * cs [0x53bc,0x544d) / file [0x55bc,0x564d), 145 bytes. Strict match: tools/match_function.py.
 *
 * Mouse configuration screen: opens a 24x5 text window, prints the five
 * 'Mouse Configuration' lines, waits (F_7005) for a digit 1-9 (ESC counts as
 * '5'), sets the mouse dead-zone/sensitivity D_130E = 15 - digit, clears the
 * window (F_6EB9), then resets the mouse driver (INT 33h AX=0) and centres
 * the cursor (AX=4, CX=320, DX=100).
 *
 * Evidence for the name: strings 'Mouse Configuration'/'Choose the
 * sensitivity', INT 33h calls; D_130E is the threshold used by F_6505.
 *
 * Codegen: String literals land in this module's _DATA at DS:0x1044 in
 * source order.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name config_mouse
 */

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
