/*
 * F_4D9C -- draw_actors()
 * cs [0x4b9c,0x4c69) / file [0x4d9c,0x4e69), 205 bytes.
 * Strict match: tools/match_function.py.
 *
 * Per-frame sprite pass: if the playfield offset DS:0x56EC > 15 and bit 5
 * of DS:0x6156 is set, calls F_1C6A; draws each of 4 active entries of the
 * parallel arrays at DS:0x5742 (flag) / 0x574A (x) / 0x5752 (y) /
 * 0x576A (sprite); calls F_3205(i) for each active 14-byte record of
 * DS:0x56F6 (5 entries); then draws each active 314-byte record of
 * DS:0x4F8E (6 entries) at its (x, y) with sprite
 * DS:0x035E[DS:0x4F86 * 4 + frame].
 *
 * @name draw_actors
 */
/* @flags -G */

struct obj {
    int active;
    int f2, f4, f6, f8, fa;
    int id;
};

struct actor {
    int active;
    int x;
    int y;
    int frame;
    char rest[306];
};

extern int D_56EC;
extern int D_6156;
extern int D_5742[];
extern int D_574A[];
extern int D_5752[];
extern int D_576A[];
extern struct obj D_56F6[];
extern struct actor D_4F8E[];
extern int D_4F86;
extern int D_035E[];

void F_1C6A(void);
void F_1BD6(int x, int y, int sprite);
void F_3205(int i);

void F_4D9C(void)
{
    int i;

    if (D_56EC > 15 && (D_6156 & 0x20))
        F_1C6A();
    for (i = 0; i < 4; i++)
        if (D_5742[i] == 1)
            F_1BD6(D_574A[i], D_5752[i], D_576A[i]);
    for (i = 0; i < 5; i++)
        if (D_56F6[i].active == 1)
            F_3205(i);
    for (i = 0; i < 6; i++)
        if (D_4F8E[i].active == 1)
            F_1BD6(D_4F8E[i].x, D_4F8E[i].y, D_035E[D_4F86 * 4 + D_4F8E[i].frame]);
}
