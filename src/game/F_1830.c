/*
 * F_1830 -- spawn_explosion
 * cs [0x1630,0x16f6) / file [0x1830,0x18f6), 198 bytes.
 *
 * Finds a free slot among the 6 0x13A-byte objects at D_4F8E, fills in
 * x, y, kind and the animation counters (0x6E frames, 13-frame step),
 * draws its first frame, and for kind 5 sets D_6546 = 300.
 * @name spawn_explosion -- evidence: short-lived animated object (F_18F6
 * ages and frees it); kind 5 arms the 300-frame death timer.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 */

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
