/* @flags -G */
/* @seg _DATA 0x07d4 */
extern int D_8B32;
extern int D_00AA;
extern int D_4F86;
extern int D_56F4;
extern int D_0336[];
extern int D_033C[];
extern int D_573E;
extern int D_57E4;
extern int D_5742[];
extern int D_576A[];
extern int D_1392;
extern int D_8A12;
extern int D_8A14;
extern int D_8A22;
/* The module's string literals live in its literal pool, which is not
   contiguous with this function's SCOPY initialiser at DS 0x07D4:
     D_0D6A = "     BY JOHN ROMERO\n\r"
     D_0D80 = " (C) 1990 SOFTDISK, INC.\n\r"
     D_0D9B = "PRESS THE F1 KEY FOR HELP"                                   */
extern char D_0D6A[];
extern char D_0D80[];
extern char D_0D9B[];
void F_6D64(int);
void F_95D1(void);
void F_9211(void);
void F_376E(void);
void F_0BB2(void);
void F_8EDA(void);
void F_4D9C(void);
void F_088E(int);
void F_7071(char *);
void F_92D6(int, int, int);

void F_13FF(void)
{
    char tiles[7][10] = {
        {0x12, 0x00, 0x12, 0x12, 0x12, 0x12, 0x00, 0x12, 0x00, 0x12},
        {0x12, 0x00, 0x12, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00, 0x12},
        {0x12, 0x00, 0x12, 0x00, 0x00, 0x12, 0x12, 0x12, 0x00, 0x12},
        {0x12, 0x00, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x32, 0x12},
        {0x12, 0x00, 0x12, 0x06, 0x12, 0x12, 0x12, 0x00, 0x00, 0x12},
        {0x12, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x12},
        {0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x12, 0x06, 0x12},
    };
    int i;
    int j;

    F_6D64(D_8B32);
    if (D_8B32 == 2)
        F_95D1();
    if (D_00AA < 3) {
        F_9211();
        F_376E();
        F_0BB2();
        F_8EDA();
        D_573E = D_0336[D_4F86];
        D_57E4 = D_033C[D_4F86];
        for (i = 0; i < 4; i++) {
            if (D_5742[i]) {
                switch (D_4F86) {
                case 0: D_576A[i] = (D_56F4 - 2) * 8 + 0x7d; break;
                case 1: D_576A[i] = (D_56F4 - 2) * 8 * 2 + 0xc5; break;
                case 2: D_576A[i] = (D_56F4 - 2) * 4 + 0x59; break;
                }
            }
        }
        F_4D9C();
        if (D_00AA == 2)
            F_088E(0);
    }
    if (D_00AA == 3) {
        D_1392 = -1;
        D_8A12 = 8;
        D_8A22 = 8;
        D_8A14 = 6;
        F_7071(D_0D6A);
        F_7071(D_0D80);
        D_8A14 = 0x15;
        F_7071(D_0D9B);
        D_1392 = 0;
        for (i = 0; i < 10; i++)
            for (j = 0; j < 7; j++)
                F_92D6(i + 5, j + 3, tiles[j][i]);
    }
}
