/* @flags -G */
struct obj {
    int active;
    int x;
    int y;
    int f6;
    int f8;
    int fa;
    int type;
    char rest[0x13a - 14];
};
extern struct obj D_4F8E[];
extern int D_4F86;
extern int D_035E[][4];
extern int D_6546;
void F_1BD6(int, int, int);

void F_1830(int x, int y, int type)
{
    int i;

    for (i = 0; i < 6; i++) {
        if (D_4F8E[i].active == 0) {
            D_4F8E[i].x = x;
            D_4F8E[i].y = y;
            D_4F8E[i].type = type;
            D_4F8E[i].active = 1;
            D_4F8E[i].f6 = 0;
            D_4F8E[i].f8 = 0x6e;
            D_4F8E[i].fa = 0xd;
            F_1BD6(x, y, D_035E[D_4F86][0]);
            if (type == 5)
                D_6546 = 300;
            break;
        }
    }
}
