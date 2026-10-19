/*
 * F_5DD5 -- control_panel
 * cs [0x5bd5,0x5e99) / file [0x5dd5,0x6099), 708 bytes. Strict match: tools/match_function.py.
 *
 * Control-panel main loop (F2 menu): saves current settings, sets the video
 * mode, draws the panel, then moves a cursor over the option grid with the
 * arrow keys (skipping unavailable options), ENTER applies the option (video
 * mode switch incl. EGA plane upload, sound choice, control choice which
 * runs the keyboard/mouse/joystick configuration screens), ESC writes the
 * choices back (D_12F2 control, D_8B32 video, D_137E sound) and returns.
 *
 * Evidence for the name: arrow scan codes 0x48/0x50/0x4B/0x4D, calls
 * config_keyboard/config_mouse/F_53C3(joystick), draw_control_panel.
 *
 * Codegen: Chained assignments `D_85FC = D_65D8 = D_8B32` store the inner
 * target first. `while (!D_65B0[r][--c]);` gives the empty-body while (eb
 * 00). `if (--D_8A0A < 0)` uses the dec flags directly, `if (++D_8A0A > 2)`
 * reloads.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name control_panel
 */

extern int D_8A12, D_8A14;
extern int D_8B32, D_137E, D_12F2, D_12F4;
extern int D_65D8, D_65FA, D_8600, D_8602;
extern int D_85FC, D_8A08, D_8A0E, D_8A10;
extern int D_8A0A, D_6554;
extern int D_0F02[];                    /* menu rows */
extern int D_0F0A[];                    /* menu option columns */
extern int D_65B0[][5];                 /* option available flags [row][col] */
void F_6A26(void);
void F_76BF(void);
void F_76E1(void);
void F_6D64(int mode);
void F_6DC2(int x1, int y1, int x2, int y2);
void F_5B10(void);
int F_7005(void);
void F_7878(int x, int y, int c);
void F_1321(void);
void F_6213(void);
void F_5815(void);
void F_55BC(void);
void F_53C3(int stick);
void F_13FF(void);

void F_5DD5(void)
{
    char ascii, scan;
    register int key;

    F_6A26();
    F_76BF();
    D_85FC = D_65D8 = D_8B32;
    D_8A08 = D_65FA = D_137E;
    D_8A0E = D_8600 = D_12F2;
    D_8A10 = D_8602 = D_12F4;
    F_6D64(D_8B32);
    F_6DC2(0, 0, 39, 24);
    F_5B10();
    D_8A0A = 0;
    D_6554 = D_8B32 - 1;
    do {
        D_8A12 = D_0F0A[D_6554] + 2;
        D_8A14 = D_0F02[D_8A0A] + 3;
        key = F_7005();
        ascii = key % 256;
        scan = key / 256;
        if (scan == 0x48) {
            if (--D_8A0A < 0)
                D_8A0A = 2;
        }
        if (scan == 0x50) {
            if (++D_8A0A > 2)
                D_8A0A = 0;
        }
        while (!D_65B0[D_8A0A][D_6554])
            D_6554--;
        if (scan == 0x4b) {
            if (D_6554 == 0)
                D_6554 = 4;
            while (!D_65B0[D_8A0A][--D_6554])
                ;
        }
        if (scan == 0x4d) {
            while (!D_65B0[D_8A0A][++D_6554] || D_6554 > 3)
                if (D_6554 == 4)
                    D_6554 = -1;
        }
        if (ascii == 13) {
            switch (D_8A0A) {
            case 0:
                if (D_6554 + 1 == D_85FC)
                    break;
                F_7878(D_0F0A[D_85FC - 1] + 1, D_0F02[D_8A0A] + 3, ' ');
                D_8B32 = D_85FC = D_6554 + 1;
                F_1321();
                F_6D64(D_8B32);
                if (D_8B32 == 2)
                    F_6213();
                F_6DC2(0, 0, 39, 24);
                F_5B10();
                break;
            case 1:
                F_7878(D_0F0A[D_8A08] + 1, D_0F02[D_8A0A] + 3, ' ');
                D_8A08 = D_6554;
                break;
            case 2:
                F_7878(D_0F0A[D_8A0E] + 1, D_0F02[D_8A0A] + 3, ' ');
                D_8A0E = D_6554;
                if (D_8A0E == 0)
                    F_5815();
                else if (D_8A0E == 1)
                    F_55BC();
                else if (D_8A0E == 2)
                    F_53C3(1);
                else if (D_8A0E == 3)
                    F_53C3(2);
                F_5B10();
                break;
            }
            F_7878(D_0F0A[D_6554] + 1, D_0F02[D_8A0A] + 3, 15);
        }
    } while (ascii != 27);
    D_12F2 = D_8A0E;
    D_12F4 = D_8A10;
    D_8B32 = D_85FC;
    D_137E = D_8A08;
    F_13FF();
    F_76E1();
}
