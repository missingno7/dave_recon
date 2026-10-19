/* @flags -G */
/* @seg-blocked _DATA 0x07c2 */
struct hiscore {
    char level;
    char score[5];
    char name[3];
};
extern struct hiscore *D_4F8C;
extern int D_8A12;
extern int D_8A14;
extern int D_8A22;
/* The module's string literals live in its literal pool (DS 0x08AF..), which
   is not contiguous with the SCOPY initialiser at DS 0x07C2, so they are
   referenced by address here:
     D_08D0 = "High Scores\r\n\nScore  Name  Level\r\n-----  ----  -----\r\n"
     D_0907 = "\n\n\r"                                                        */
extern char D_08D0[];
extern char D_0907[];
void F_770A(void);
void F_763E(int);
void F_6EF1(int, int);
void F_7071(char *);

void F_088E(int flag)
{
    int k;
    int i;

    F_770A();
    if (flag)
        F_763E(0xb);
    for (i = 4; i < 0x1a; i += 2)
        F_6EF1(i, i / 2);
    D_8A12 = 0x10;
    D_8A14 = 6;
    D_8A22 = 0xc;
    F_7071(D_08D0);
    for (i = 0; i < 5; i++) {
        char buf[6] = "";
        char lvl;

        if (flag)
            F_763E(6);
        for (k = 0; k < 5; k++)
            buf[k] = D_4F8C[i].score[k] + '0';
        F_7071(buf);
        for (k = 0; k < 3; k++)
            buf[k] = D_4F8C[i].name[k];
        buf[3] = 0;
        D_8A12 = 0x13;
        F_7071(buf);
        lvl = D_4F8C[i].level;
        buf[0] = lvl + '0';
        buf[1] = 0;
        D_8A12 = 0x1b;
        if (lvl == 10) {
            buf[0] = '1';
            buf[1] = '0';
            buf[2] = 0;
        }
        if (lvl == 11) {
            buf[0] = 'w';
            buf[1] = 'o';
            buf[2] = 'n';
            buf[3] = 0;
            D_8A12--;
        }
        F_7071(buf);
        F_7071(D_0907);
        if (flag)
            F_770A();
    }
}
