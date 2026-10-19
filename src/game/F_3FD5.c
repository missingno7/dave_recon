/*
 * F_3FD5 -- pick_up_items()
 * cs [0x3dd5,0x44b0) / file [0x3fd5,0x46b0), 1755 bytes.
 * Strict match: tools/match_function.py.
 *
 * While Dave is alive (bit 5 of DS:0x6156) and inside the playfield
 * (16 < y < 0xA6), looks at the 2x2 tiles under him (grid DS:0x57A8, row
 * offsets DS:0x13DD) and, for each, against the 10 collectible tile ids
 * DS:0x023A[k] (values DS:0x024E[k]): a non-door item adds its value to
 * the score DS:0x4C60 (long; F_0C34 handles extra lives), plays sound 6
 * and is removed from the grid and the screen. Then per item type:
 * 10 = trophy (sets DS:0x4F88, sound 7, stops the trophy's animated-tile
 * entries, shows the "go thru the door" sprite), 2 = door (only with the
 * trophy: sets the level-done flag DS:0x6158 and adds the door value),
 * 20 = gun (DS:0x4F84, sprite, sound 12), 4 = jetpack (fuel meter
 * DS:0x5798 = 60, DS:0x6154 = 15, DS:0x4F8A, sound 12).
 *
 * @name pick_up_items
 *
 * Codegen notes: the per-tile block is written once as a macro and
 * expanded four times (tile offsets 0, 1, 100, 101); the original has
 * four identical copies, so it was either a macro or copy-paste.
 */


struct anim {
    int active;
    int first;
    int cur;
    int col;
    int row;
    int count;
};

extern int D_6156;
extern int D_56EA;
extern int D_56EC;
extern int D_57A0;
extern int D_13DD[];
extern char *D_57A8;
extern int D_023A[];            /* collectible tile ids */
extern int D_024E[];            /* their point values */
extern long D_4C60;             /* g_score */
extern int D_4F88;              /* has trophy */
extern int D_4F84;              /* has gun */
extern int D_4F8A;              /* has jetpack */
extern int D_6158;              /* level done */
extern struct anim D_57E8[];
extern int D_4F86;
extern int D_0208;
extern int D_020A[];
extern int D_020C[];
extern int D_0214[];
extern int D_5798;              /* jetpack fuel meter */
extern int D_6154;

void F_0C34(void);
void F_769B(void);
void F_763E(int snd);
void F_1C28(void);
void F_1C6A(void);
void F_92D6(int x, int y, int tile);
void F_1BD6(int x, int y, int sprite);
void F_371F(void);

#define PICK(t, o, dx, dy)                                              \
    if (D_023A[k] == t) {                                               \
        if (t != 2) {                                                   \
            D_4C60 += D_024E[k];                                        \
            F_0C34();                                                   \
            F_769B();                                                   \
            F_763E(6);                                                  \
            *(D_57A8 + pos + o) = 0;                                           \
            F_1C28();                                                   \
            F_92D6(col - D_57A0 + dx, row + dy, 0);                     \
            F_1C6A();                                                   \
        }                                                               \
        switch (t) {                                                    \
        case 10:                                                        \
            if (D_4F88 == 0) {                                          \
                D_4F88 = 1;                                             \
                F_763E(7);                                              \
                for (i = 0; D_57E8[i].count > 0; i++)                   \
                    if (D_57E8[i].first == 10)                          \
                        D_57E8[i].active = 0;                           \
                F_1BD6(0x48, 0xb8, D_0214[D_4F86 * D_0208]);            \
            }                                                           \
            break;                                                      \
        case 2:                                                         \
            if (D_4F88 == 1) {                                          \
                D_6158 = 1;                                             \
                D_4C60 += D_024E[k];                                    \
                F_0C34();                                               \
            }                                                           \
            break;                                                      \
        case 20:                                                        \
            D_4F84 = 1;                                                 \
            F_1BD6(0xf0, 0xaa, D_020C[D_4F86 * D_0208]);                \
            F_763E(12);                                                 \
            break;                                                      \
        case 4:                                                         \
            if (D_4F8A != 1)                                            \
                F_1BD6(0, 0xaa, D_020A[D_4F86 * D_0208]);               \
            if (D_4F8A == 1)                                            \
                F_371F();                                               \
            D_5798 = 60;                                                \
            D_6154 = 15;                                                \
            F_371F();                                                   \
            D_4F8A = 1;                                                 \
            F_763E(12);                                                 \
            break;                                                      \
        }                                                               \
    }

void F_3FD5(void)
{
    int t00, t01, t10, t11;
    int col, row, pos;
    int i, k;

    if ((D_6156 & 0x20) && D_56EC > 16 && D_56EC < 0xa6) {
        col = D_56EA / 16 + D_57A0;
        row = (D_56EC - 16) / 16;
        pos = D_13DD[row] + col;
        t00 = D_57A8[pos];
        t01 = *(D_57A8 + pos + 1);
        t10 = *(D_57A8 + pos + 100);
        t11 = *(D_57A8 + pos + 101);
        for (k = 0; k < 10; k++) {
            PICK(t00, 0, 0, 0)
            PICK(t01, 1, 1, 0)
            PICK(t10, 100, 0, 1)
            PICK(t11, 101, 1, 1)
        }
    }
}
