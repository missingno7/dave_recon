/*
 * F_301B -- move_bullets()
 * cs [0x2e1b,0x3005) / file [0x301b,0x3205), 490 bytes.
 * Strict match: tools/match_function.py.
 *
 * Steps each active record of the 5-entry, 14-byte object table at
 * DS:0x56F6 (bullets): direction flag (+6) 0 moves 2 px left, 1 moves 2 px
 * right. A bullet that hits a solid tile (F_2D38 attribute 1 at x-2 or
 * x+16, y+1) is deactivated after being erased with F_3205; otherwise it
 * is erased, its frame (+8) advances every 3rd tick (shared countdown
 * DS:0x5796), it moves, and kind-1 bullets that leave the screen
 * (x < 0 or x > 320) are dropped; the rest are redrawn (F_3205).
 *
 * @name move_bullets
 */


struct obj {
    int active;
    int x;
    int y;
    int dir;
    int frame;
    int kind;
    int id;
};

extern struct obj D_56F6[];
extern int D_5796;              /* bullet animation countdown */

int F_2D38(int x, int y, int dx, int dy);
void F_3205(int i);

void F_301B(void)
{
    int x;
    int i;
    int y;

    for (i = 0; i < 5; i++) {
        if (D_56F6[i].active == 1) {
            x = D_56F6[i].x;
            y = D_56F6[i].y;
            switch (D_56F6[i].dir) {
            case 0:
                if (F_2D38(x, y, -2, 1) == 1) {
                    D_56F6[i].active = 0;
                    F_3205(i);
                    break;
                }
                F_3205(i);
                if (--D_5796 == 0) {
                    D_5796 = 3;
                    D_56F6[i].frame = ++D_56F6[i].frame & 3;
                }
                D_56F6[i].x -= 2;
                if (D_56F6[i].kind == 1 && (D_56F6[i].x < 0 || D_56F6[i].x > 0x140)) {
                    D_56F6[i].active = 0;
                    break;
                }
                F_3205(i);
                break;
            case 1:
                if (F_2D38(x, y, 16, 1) == 1) {
                    D_56F6[i].active = 0;
                    F_3205(i);
                    break;
                }
                F_3205(i);
                if (--D_5796 == 0) {
                    D_5796 = 3;
                    D_56F6[i].frame = ++D_56F6[i].frame & 3;
                }
                D_56F6[i].x += 2;
                if (D_56F6[i].kind == 1 && (D_56F6[i].x < 0 || D_56F6[i].x > 0x140)) {
                    D_56F6[i].active = 0;
                    break;
                }
                F_3205(i);
                break;
            }
        }
    }
}
