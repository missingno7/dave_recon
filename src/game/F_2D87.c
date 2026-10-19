/*
 * F_2D87 -- move_monsters()
 * cs [0x2b87,0x2e1b) / file [0x2d87,0x2e1b), 660 bytes.
 * Strict match: tools/match_function.py.
 *
 * Steps each of the 4 monster slots (parallel int arrays: active 0x5742,
 * x 0x574A, y 0x5752, path index 0x575A, fire reload 0x5762, sprite
 * 0x576A, anim countdown 0x5772, anim frame 0x577A, fire countdown 0x5782,
 * move countdown 0x578A). Every 5th tick an active monster is erased
 * (redrawn with F_1BD6, XOR-style), moved along the level's movement path
 * (huge char pointer DS:0x614C, (dx, dy) byte pairs, 0xEA = restart),
 * gets its sprite id recomputed per graphics mode DS:0x4F86 from the
 * current level DS:0x56F4 and anim frame, and is drawn again; the frame
 * advances every 2nd step. A visible monster with no live bullet
 * (F_483F(i + 1)) fires when its countdown expires and bit 5 of DS:0x6156
 * is set: F_4886 spawns the bullet left or right of it depending on the
 * player x DS:0x56EA, at y + DS:0x0156[level] / 2 - 2 (right side offset
 * DS:0x0146[level]).
 *
 * @name move_monsters
 *
 * Codegen notes: the path index is unsigned (index extension `xor cx,cx`
 * before N_PADD@ -- the pointer is huge). `p[n]` is one PADD; the y step
 * `*(p + n + 1)` is two PADDs. `a[i] = ++a[i] & 3` keeps BX between the
 * `inc` and the reload. `x * 16` compiles to `mov cl,4; shl dx,cl`; the
 * original's four `shl dx,1` need a split constant (`* 8 * 2`). The last
 * switch case has no `break` (no jmp to the switch end).
 */


extern int D_5742[];            /* active */
extern int D_574A[];            /* x */
extern int D_5752[];            /* y */
extern unsigned D_575A[];       /* path index */
extern int D_5762[];            /* fire reload time */
extern int D_576A[];            /* sprite id */
extern int D_5772[];            /* anim countdown */
extern int D_577A[];            /* anim frame */
extern int D_5782[];            /* fire countdown */
extern int D_578A[];            /* move countdown */
extern char huge *D_614C;       /* monster movement path */
extern int D_4F86;              /* graphics-mode index */
extern int D_56F4;              /* g_current_level */
extern int D_56EA;              /* player x */
extern int D_6156;
extern int D_0146[];
extern int D_0156[];

void F_1BD6(int x, int y, int sprite);
int F_483F(int id);
void F_4886(int x, int y, int flag, int kind, int id);

void F_2D87(void)
{
    int i;
    unsigned idx;

    for (i = 0; i < 4; i++) {
        if (D_5742[i] != 0 && --D_578A[i] == 0) {
            D_578A[i] = 5;
            F_1BD6(D_574A[i], D_5752[i], D_576A[i]);
            idx = D_575A[i];
            if (D_614C[idx] == -22) {
                D_575A[i] = 0;
                idx = 0;
            }
            D_574A[i] += D_614C[idx];
            D_5752[i] += *(D_614C + idx + 1);
            D_575A[i] += 2;
            switch (D_4F86) {
            case 0:
                D_576A[i] = D_577A[i] * 2 + (D_56F4 - 2) * 8 + 0x7d;
                break;
            case 1:
                D_576A[i] = D_577A[i] * 4 + (D_56F4 - 2) * 8 * 2 + 0xc5;
                break;
            case 2:
                D_576A[i] = D_577A[i] + (D_56F4 - 2) * 4 + 0x59;
            }
            F_1BD6(D_574A[i], D_5752[i], D_576A[i]);
            if (--D_5772[i] == 0) {
                D_5772[i] = 2;
                D_577A[i] = ++D_577A[i] & 3;
            }
            if (D_574A[i] < 0x154 && D_574A[i] >= 0 && !F_483F(i + 1) &&
                --D_5782[i] < 1 && (D_6156 & 0x20)) {
                D_5782[i] = D_5762[i];
                if (D_574A[i] > D_56EA)
                    F_4886(D_574A[i] - 16, D_5752[i] + D_0156[D_56F4] / 2 - 2, 0, 0, i + 1);
                else
                    F_4886(D_574A[i] + D_0146[D_56F4], D_5752[i] + D_0156[D_56F4] / 2 - 2, 1, 0, i + 1);
            }
        }
    }
}
