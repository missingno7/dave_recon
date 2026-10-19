/* @flags -G */
/* @seg _DATA 0x1243 */
extern int D_8A12, D_8A14, D_8A22;
extern int D_1392;
extern int D_0F02[];                    /* menu rows: video, sound, control */
extern int D_0F0A[];                    /* menu option columns */
extern int D_654C, D_654E, D_6550, D_6552, D_6556;
extern int D_85FC, D_8A08, D_8A0E;
void F_7071(char *s);
void F_7878(int x, int y, int c);
void F_59EC(void);
void F_7B3B(int x, int y, int icon);

void F_5B10(void)
{
    D_8A22 = 1;
    D_1392 = 0;
    D_8A12 = 8;
    D_8A14 = 2;
    F_7071("PC-Arcade Control Panel\n\r");
    F_59EC();

    D_8A14 = D_0F02[0] + 2;
    D_8A12 = 2;
    F_7071("VIDEO:");
    F_7B3B(D_0F0A[0] * 8, D_0F02[0] * 8, 0);
    if (D_654C)
        F_7B3B(D_0F0A[1] * 8, D_0F02[0] * 8, 1);
    else
        F_7B3B(D_0F0A[1] * 8, D_0F02[0] * 8, 3);
    if (D_654E)
        F_7B3B(D_0F0A[2] * 8, D_0F02[0] * 8, 2);
    else
        F_7B3B(D_0F0A[2] * 8, D_0F02[0] * 8, 4);

    D_8A14 = D_0F02[1] + 2;
    D_8A12 = 2;
    F_7071("SOUND:");
    F_7B3B(D_0F0A[0] * 8, D_0F02[1] * 8, 5);
    F_7B3B(D_0F0A[1] * 8, D_0F02[1] * 8, 6);

    D_8A14 = D_0F02[2] + 2;
    D_8A12 = 2;
    F_7071("CONTROL:");
    F_7B3B(D_0F0A[0] * 8, D_0F02[2] * 8, 7);
    if (D_6556)
        F_7B3B(D_0F0A[1] * 8, D_0F02[2] * 8, 10);
    else
        F_7B3B(D_0F0A[1] * 8, D_0F02[2] * 8, 12);
    if (D_6550)
        F_7B3B(D_0F0A[2] * 8, D_0F02[2] * 8, 8);
    else
        F_7B3B(D_0F0A[2] * 8, D_0F02[2] * 8, 11);
    if (D_6552)
        F_7B3B(D_0F0A[3] * 8, D_0F02[2] * 8, 9);
    else
        F_7B3B(D_0F0A[3] * 8, D_0F02[2] * 8, 11);

    F_7878(D_0F0A[D_85FC - 1] + 1, D_0F02[0] + 3, 15);
    F_7878(D_0F0A[D_8A08] + 1, D_0F02[1] + 3, 15);
    F_7878(D_0F0A[D_8A0E] + 1, D_0F02[2] + 3, 15);
    D_8A14 = 21;
    D_8A12 = 1;
    F_7071("  Move the cursor with the arrow keys \n\r");
    F_7071("   Make decisions with the ENTER key  \n\r");
    F_7071("       ESC to return to your game     \n\r");
}
