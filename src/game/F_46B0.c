/*
 * F_46B0 -- scroll_if_needed()
 * cs [0x44b0,0x45f8) / file [0x46b0,0x47f8), 328 bytes.
 * Strict match: tools/match_function.py.
 *
 * Horizontal scrolling. When the player's x (DS:0x56EA) passes 0x118 and
 * the view column DS:0x57A0 is below 80 (100-column level, 20 visible),
 * scrolls right 15 columns, one per frame: the view column is incremented,
 * every on-screen entity x (DS:0x574A[4], object table DS:0x56F6, actor
 * table DS:0x4F8E) and the player x move 16 pixels left, and the frame is
 * redrawn (F_7831, F_8EDA, F_4D9C). Stops early at column 80. When the
 * player x drops below 0x20 and the view column is > 0 it scrolls left the
 * same way. Both directions bracket the work with F_76BF / F_76E1 and, if
 * DS:0x56EC < 16, F_1C28 / F_1C6A.
 *
 * @name scroll_screen
 *
 * Codegen notes: the early exit is `j = 15;` in an else branch (the loop
 * ends with `mov di,0xf; inc di`).
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

struct actor {
    int active;
    int x;
    int y;
    int frame;
    char rest[306];
};

extern int D_56EA;              /* player x (pixels, screen-relative) */
extern int D_56EC;
extern int D_57A0;              /* first visible level column */
extern int D_574A[];
extern struct obj D_56F6[];
extern struct actor D_4F8E[];

void F_76BF(void);
void F_76E1(void);
void F_1C28(void);
void F_1C6A(void);
void F_7831(void);
void F_8EDA(void);
void F_4D9C(void);

void F_46B0(void)
{
    int i, j;

    if (D_56EA > 0x118 && D_57A0 < 80) {
        F_76BF();
        if (D_56EC < 16)
            F_1C28();
        for (j = 0; j < 15; j++) {
            if (D_57A0 < 80) {
                D_57A0++;
                for (i = 0; i < 4; i++)
                    D_574A[i] -= 16;
                for (i = 0; i < 5; i++)
                    D_56F6[i].x -= 16;
                for (i = 0; i < 6; i++)
                    D_4F8E[i].x -= 16;
                D_56EA -= 16;
                F_7831();
                F_8EDA();
                F_4D9C();
            } else
                j = 15;
        }
        F_76E1();
        if (D_56EC < 16)
            F_1C6A();
    } else if (D_56EA < 0x20 && D_57A0 > 0) {
        if (D_56EC < 16)
            F_1C28();
        F_76BF();
        for (j = 0; j < 15; j++) {
            if (D_57A0 > 0) {
                D_57A0--;
                for (i = 0; i < 4; i++)
                    D_574A[i] += 16;
                for (i = 0; i < 5; i++)
                    D_56F6[i].x += 16;
                for (i = 0; i < 6; i++)
                    D_4F8E[i].x += 16;
                D_56EA += 16;
                F_7831();
                F_8EDA();
                F_4D9C();
            } else
                j = 15;
        }
        F_76E1();
        if (D_56EC < 16)
            F_1C6A();
    }
}
