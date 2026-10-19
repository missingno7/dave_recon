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
