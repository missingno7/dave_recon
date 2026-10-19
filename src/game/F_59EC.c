/*
 * F_59EC -- detect_hardware
 * cs [0x57ec,0x5910) / file [0x59ec,0x5b10), 292 bytes. Strict match: tools/match_function.py.
 *
 * Builds the control-panel availability tables: EGA/VGA flags from adapter
 * type D_9EC0 (3/5 => EGA, 5/4 => VGA), fills video/sound row D_65B0[0..9],
 * probes joysticks 1 and 2 with read_joystick_axes (x < 500 => present), and
 * detects a mouse driver (INT 33h vector non-NULL and its first byte not
 * IRET 0xCF); fills control row D_65C4[0..4].
 *
 * Evidence for the name: INT 33h vector check, joystick probe, consumer
 * F_5B10/F_5DD5 (option grid D_65B0[3][5]).
 *
 * Codegen: `(*(int far *)v & 0xff) == 0xcf` gives les bx / mov ax,es:[bx] /
 * and ax,0xff.
 *
 * Built with -G (speed opt: `inc sp; inc sp` instead of `pop cx` for 2-byte
 * arg cleanup).
 * @name detect_hardware
 */

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
