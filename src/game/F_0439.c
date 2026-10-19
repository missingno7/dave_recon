/*
 * F_0439 -- main
 * cs [0x0239,0x02d2) / file [0x439,0x4d2), 153 bytes.
 *
 * C main(). Initialises (F_519B), detects the display adapter (F_7C59 ->
 * D_9EC0: 3 = EGA, 4/5 = VGA/MCGA, else CGA) and stores the video mode in
 * D_8B32 (1 CGA, 2 EGA, 3 VGA), loads the graphics (F_1321), then loops:
 * state 3 (title) -> per-frame pipeline (attract F_09DE, input F_4A27, the
 * big F_1D16, monsters/shots/doors ... F_15A5 death handling) until
 * D_5792 (game over); then high-score check F_04FC unless quitting
 * (D_579C), and finally exit via F_04D2(0).
 * @name main -- evidence: C0S calls it (layout/symbols.json).
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 * switch cases are emitted in source order (4,5 / 3 / default) while the
 * compare chain is sorted ascending (3,4,5).
 */
/* @flags -G */
extern int D_9EC0;
extern int D_8B32;
extern int D_00AA;
extern int D_5792;
extern int D_579C;
void F_519B(void);
int F_7C59(void);
void F_1321(void);
void F_09DE(void);
void F_4A27(void);
void F_1D16(void);
void F_18F6(void);
void F_2D87(void);
void F_301B(void);
void F_332C(void);
void F_37ED(void);
void F_3FD5(void);
void F_3BA3(void);
void F_34CB(void);
void F_1780(void);
void F_15A5(void);
void F_04FC(void);
void F_04D2(int);

void main(void)
{
    F_519B();
    D_9EC0 = F_7C59();
    switch (D_9EC0) {
    case 4:
    case 5:
        D_8B32 = 3;
        break;
    case 3:
        D_8B32 = 2;
        break;
    default:
        D_8B32 = 1;
        break;
    }
    F_1321();
    do {
        D_00AA = 3;
        do {
            F_09DE();
            F_4A27();
            F_1D16();
            F_18F6();
            F_2D87();
            F_301B();
            F_332C();
            F_37ED();
            F_3FD5();
            F_3BA3();
            F_34CB();
            F_1780();
            F_15A5();
        } while (D_5792 == 0);
        D_5792 = 0;
        if (D_579C == 0)
            F_04FC();
    } while (D_579C == 0);
    F_04D2(0);
}
