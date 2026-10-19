/* @flags -G */
#include <bios.h>
#include <stdlib.h>
#include <time.h>
struct joy {
    int a;
    int b;
    int c;
};
extern int D_00AA;
extern int D_4F86;
extern int D_01F0[];
extern char far *D_57A4;
extern int D_57A2;
extern int D_56F4;
void F_088E(int);
void F_7831(void);
void F_4997(void);
struct joy F_688C(int);
void F_535A(void);
void F_4E69(void);
void F_13FF(void);
void F_3435(void);
void F_1B84(int, int, int);
void F_92D6(int, int, int);

void F_09DE(void)
{
    int flag;
    struct joy s;
    int i;
    int j;

    switch (D_00AA) {
    case 2:
        F_088E(1);
        for (i = 0; i < 1000; i++) {
            F_7831();
            F_4997();
            s = F_688C(1);
            if (flag = bioskey(1) || s.b)
                break;
        }
        if (flag) {
            D_00AA = 0;
            F_535A();
            F_4E69();
            F_13FF();
            F_3435();
            break;
        }
        D_00AA++;
    case 3:
        F_13FF();
        for (i = 0; i < 200; i++) {
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_4997();
            F_1B84(0x68, 0, D_01F0[D_4F86 * 4 + (i & 3)]);
            j++;
            F_92D6(8, 7, (j & 3) + 6);
            F_92D6(0xd, 9, (j & 3) + 6);
            s = F_688C(1);
            if (flag = bioskey(1) || s.b)
                break;
        }
        F_535A();
        if (flag) {
            D_00AA = 0;
            F_4E69();
            F_13FF();
            F_3435();
            break;
        }
        srand(time(NULL));
        D_57A2 = *(int far *)(D_57A4 + (int)((long)rand() * *D_57A4 / 32767) * 4 + 4);
        D_00AA = 1;
        D_56F4 = D_57A4[D_57A2];
        D_57A2++;
        F_4E69();
        F_13FF();
    }
}
