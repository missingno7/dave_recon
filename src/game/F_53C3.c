/*
 * F_53C3 -- calibrate_joystick(stick)
 * cs [0x51c3,0x53bc) / file [0x53c3,0x55bc), 505 bytes.
 * Strict match: tools/match_function.py (also verifies the 8 prompt
 * strings, the candidate's _DATA, against DS:0x0F92..).
 *
 * Joystick calibration screen. Prints the "Joystick Configuration" prompt
 * (F_6EF1 positions the text cursor at 24, 9; F_7071 prints), then
 * asks for the upper-left corner: while waiting, a colour-cycling
 * (15..22) marker is drawn through F_7878 at the text cursor DS:0x8A12/14,
 * the raw stick position is sampled by F_664B into (x1, y1) and the input
 * state by F_66F2(stick); fire (button word == 1) accepts, then it waits
 * for release. Same for the lower-right corner (x2, y2). The dead-zone
 * thresholds are set a quarter of the range inside each corner:
 * DS:0x12F6/0x12FC/0x1302/0x1308[stick] = x1 + dx, x2 - dx, y1 + dy,
 * y2 - dy. If DS:0x8A34 becomes non-zero (abort) the calibration is
 * skipped. Always ends with F_6A26, F_6EB9.
 *
 * @name calibrate_joystick
 *
 * Codegen notes: every struct-returning call site gets its own 6-byte
 * temporary (bp-0x18, -0x1E, -0x24, -0x2A). The abort is a `goto` to the
 * shared tail (it skips the threshold stores but not F_6A26/F_6EB9).
 */
/* @flags -G */
/* @seg _DATA 0x0f92 */

struct input {
    int dir;
    int button;
    int b2;
};

extern int D_8A12;              /* text cursor column */
extern int D_8A14;              /* text cursor row */
extern int D_8A34;              /* abort flag */
extern int D_12F6[];
extern int D_12FC[];
extern int D_1302[];
extern int D_1308[];

void F_6EF1(int col, int row);
void F_7071(char *s);
void F_7878(int col, int row, int color);
void F_7831(void);
void F_664B(int stick, int *x, int *y);
struct input F_66F2(int stick);
void F_6A26(void);
void F_6EB9(void);

void F_53C3(int stick)
{
    int dx, dy;
    int x1, y1;
    int x2, y2;
    struct input in;
    int color;

    F_6EF1(0x18, 9);
    F_7071(" Joystick Configuration\n\r");
    F_7071(" ----------------------\n\r");
    F_7071("Hold the joystick in the\n\r");
    F_7071("upper left\n\r");
    F_7071("corner and hit fire:");
    color = 15;
    do {
        F_7878(D_8A12, D_8A14, color);
        F_7831();
        F_7831();
        F_7831();
        if (++color == 0x17)
            color = 15;
        F_664B(stick, &x1, &y1);
        in = F_66F2(stick);
        if (D_8A34 != 0)
            goto done;
    } while (in.button != 1);
    F_7878(D_8A12, D_8A14, 0x20);
    do {
        in = F_66F2(stick);
    } while (in.button != 0);
    F_7831();
    F_7831();
    F_7071("\n\n\rHold the joystick in the\n\r");
    F_7071("lower right\n\r");
    F_7071("corner and hit fire:");
    do {
        F_7878(D_8A12, D_8A14, color);
        F_7831();
        F_7831();
        F_7831();
        if (++color == 0x17)
            color = 15;
        F_664B(stick, &x2, &y2);
        in = F_66F2(stick);
        if (D_8A34 != 0)
            goto done;
    } while (in.button != 1);
    F_7878(D_8A12, D_8A14, 0x20);
    do {
        in = F_66F2(stick);
    } while (in.button != 0);
    dx = (x2 - x1) / 4;
    dy = (y2 - y1) / 4;
    D_12F6[stick] = x1 + dx;
    D_12FC[stick] = x2 - dx;
    D_1302[stick] = y1 + dy;
    D_1308[stick] = y2 - dy;
done:
    F_6A26();
    F_6EB9();
}
