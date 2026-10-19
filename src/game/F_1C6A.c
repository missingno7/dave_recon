/* @flags -G */
extern int D_4F86;
extern int D_56EA;
extern int D_56EC;
extern int D_573E;
extern int D_57E4;
extern unsigned char D_4C64[];
void F_89E6(int, int, int, void *);
void F_86A9(int, int, int, void *);
void F_8871(int, int, int, void *);
void F_88FD(int, int, int, int);
void F_8525(int, int, int, int);
void F_8778(int, int, int, int);

void F_1C6A(void)
{
    switch (D_4F86) {
    case 0:
        F_89E6(D_56EA, D_56EC, D_57E4, D_4C64);
        F_88FD(D_56EA, D_56EC, D_573E, D_57E4);
        break;
    case 1:
        F_86A9(D_56EA, D_56EC, D_57E4, D_4C64);
        F_8525(D_56EA, D_56EC, D_573E, D_57E4);
        break;
    case 2:
        F_8871(D_56EA, D_56EC, D_57E4, D_4C64);
        F_8778(D_56EA, D_56EC, D_573E, D_57E4);
        break;
    }
}
