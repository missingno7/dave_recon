/*
 * F_1C6A -- draw_dave
 * cs [0x1a6a,0x1b16) / file [0x1c6a,0x1d16), 172 bytes.
 *
 * Per-video-mode: saves the background under Dave (x D_56EA, y D_56EC,
 * mask D_57E4) into D_4C64, then draws his masked sprite D_573E.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */
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
