/*
 * F_18F6 -- update_explosions
 * cs [0x16f6,0x1890) / file [0x18f6,0x1a90), 410 bytes.
 *
 * Ages each active object of F_1830: XOR-erases it, advances its 4-frame
 * animation every 13 frames, lets it fall 2 px when nothing solid is below
 * (F_2D38 probes at +4 and +14) and y < 0x98, redraws; when its life ends
 * it is erased and freed.
 * @name update_explosions
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 * the first two int locals declared get SI and DI; the third (x) stays on
 * the stack.
 */
/* @flags -G */
struct obj {
    int active;
    int x;
    int y;
    int frame;
    int life;
    int anim;
    int type;
    char rest[0x13a - 14];
};
extern struct obj D_4F8E[];
extern int D_4F86;
extern int D_035E[];
void F_1BD6(int, int, int);
int F_2D38(int, int, int, int);

void F_18F6(void)
{
    int i;
    int y;
    int x;

    for (i = 0; i < 6; i++) {
        if (D_4F8E[i].active == 1) {
            if (--D_4F8E[i].life > 0) {
                x = D_4F8E[i].x;
                y = D_4F8E[i].y;
                F_1BD6(x, y, D_035E[D_4F86 * 4 + D_4F8E[i].frame]);
                if (--D_4F8E[i].anim == 0) {
                    D_4F8E[i].frame = ++D_4F8E[i].frame & 3;
                    D_4F8E[i].anim = 0xd;
                }
                if (D_4F8E[i].anim == 0xd && F_2D38(x, y, 4, 0xe) != 1 &&
                    F_2D38(x, y, 0xe, 0xe) != 1 && y < 0x98) {
                    D_4F8E[i].y += 2;
                    y += 2;
                }
                F_1BD6(x, y, D_035E[D_4F86 * 4 + D_4F8E[i].frame]);
            } else {
                D_4F8E[i].active = 0;
                F_1BD6(D_4F8E[i].x, D_4F8E[i].y, D_035E[D_4F86 * 4 + D_4F8E[i].frame]);
            }
        }
    }
}
