/*
 * F_37ED -- check_collisions()
 * cs [0x35ed,0x39a3) / file [0x37ed,0x3ba3), 950 bytes.
 * Strict match: tools/match_function.py.
 *
 * Three collision passes, all box tests written with unsigned
 * differences (d < w covers 0 <= d < w, -d < w covers -w < d < 0):
 *  1. From level 3 on (DS:0x56F4 >= 2) while Dave is alive (bit 5 of
 *     DS:0x6156): a visible monster overlapping Dave (box from the
 *     per-level monster size tables DS:0x0146 / DS:0x0156) kills both:
 *     Dave's state bits are cleared to the 0xC0 mask, the monster is
 *     erased and deactivated, F_1C28 hides Dave and F_1830 spawns
 *     explosions at Dave (id 5) and at the monster (id i + 1); sound 8.
 *  2. If Dave's bullet (object id 5) is alive, a monster it hits is
 *     erased, the bullet is erased and freed, the monster explodes, sound
 *     8, and the score DS:0x4C60 (long) grows by (level + 1) * 100, then
 *     F_0C34 (extra-life check / score cap).
 *  3. A monster bullet (object id i + 1) hitting Dave is erased and freed,
 *     sound 8, Dave explodes and DS:0x6156 becomes 0x40 (dying).
 * The loops end early with `i = 4`.
 *
 * Codegen notes: `x &= 0xc0` compiles to `and word [x],0xc0`; the
 * original's `mov ax,[x]; and ax,0xc0; mov [x],ax` is `x = x & 0xc0`.
 * Unsigned locals give the jb/ja compares.
 *
 * @name check_collisions
 */


struct obj {
    int active;
    int x;
    int y;
    int flag;
    int frame;
    int kind;
    int id;
};

extern int D_56F4;              /* g_current_level */
extern int D_6156;
extern int D_5742[];
extern int D_574A[];
extern int D_5752[];
extern int D_576A[];
extern int D_56EA;
extern int D_56EC;
extern int D_0146[];            /* monster width per level */
extern int D_0156[];            /* monster height per level */
extern struct obj D_56F6[];
extern int D_4F86;
extern int D_01C6[];
extern int D_01CC[];
extern int D_0376[];
extern int D_038E[];
extern long D_4C60;             /* g_score */

void F_1BD6(int x, int y, int sprite);
void F_1C28(void);
void F_1830(int x, int y, int id);
void F_763E(int snd);
int F_483F(int id);
int F_47F8(int id);
void F_0C34(void);

void F_37ED(void)
{
    unsigned a, b, c;
    int i;
    unsigned d;

    if (D_56F4 >= 2 && (D_6156 & 0x20)) {
        for (i = 0; i < 4; i++) {
            if (D_5742[i] != 0 && D_574A[i] < 0x140) {
                a = D_574A[i] - D_56EA;
                d = D_5752[i] - D_56EC;
                if ((a < 13 || D_0146[D_56F4] > -a) &&
                    (d < 16 || D_0156[D_56F4] > -d)) {
                    D_6156 = D_6156 & 0xc0;
                    F_1BD6(D_574A[i], D_5752[i], D_576A[i]);
                    D_5742[i] = 0;
                    F_1C28();
                    F_1830(D_56EA, D_56EC + 3, 5);
                    F_1830(D_574A[i], D_5752[i], i + 1);
                    F_763E(8);
                }
            }
        }
    }
    if (F_483F(5) == 1) {
        for (i = 0; i < 4; i++) {
            if (D_5742[i] == 1 && D_574A[i] < 0x140) {
                d = F_47F8(5);
                a = D_56F6[d].x - D_574A[i];
                b = D_56F6[d].y - D_5752[i];
                if ((-a < 6 || D_0146[D_56F4] > a) &&
                    (-b < 3 || D_0156[D_56F4] > b)) {
                    c = D_56F6[d].flag;
                    F_1BD6(D_574A[i], D_5752[i], D_576A[i]);
                    if (c == 1)
                        c = D_01C6[D_4F86];
                    else
                        c = D_01CC[D_4F86];
                    F_1BD6(D_56F6[d].x, D_56F6[d].y, c);
                    D_56F6[d].active = 0;
                    D_5742[i] = 0;
                    F_1830(D_574A[i], D_5752[i], i + 1);
                    F_763E(8);
                    i = 4;
                    D_4C60 += (D_56F4 + 1) * 100;
                    F_0C34();
                }
            }
        }
    }
    if (D_6156 & 0x20) {
        for (i = 0; i < 4; i++) {
            if (F_483F(i + 1) == 1) {
                d = F_47F8(i + 1);
                b = D_56F6[d].x - D_56EA;
                c = D_56F6[d].y - D_56EC;
                if ((-b < 16 || b < 13) && (-c < 3 || c < 16)) {
                    a = D_0376[D_4F86 * 4 + D_56F6[d].frame];
                    if (D_56F6[d].flag == 0)
                        a = D_038E[D_4F86 * 4 + D_56F6[d].frame];
                    F_1BD6(D_56F6[d].x, D_56F6[d].y, a);
                    D_56F6[d].active = 0;
                    F_763E(8);
                    F_1C28();
                    F_1830(D_56EA, D_56EC + 3, 5);
                    D_6156 = 0x40;
                    i = 4;
                }
            }
        }
    }
}
