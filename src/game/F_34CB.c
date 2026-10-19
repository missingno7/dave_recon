/*
 * F_34CB -- check_level_exit_warp()
 * cs [0x32cb,0x351f) / file [0x34cb,0x371f), 596 bytes.
 * Strict match: tools/match_function.py.
 *
 * Called while playing: if Dave walks off the left edge of the level top
 * row (y offset DS:0x56EC < 16, view column DS:0x57A0 == 0, x DS:0x56EA
 * < 2) or off the right edge (view column 80, x > 0x132), and this is
 * neither a warp zone (DS:0x573C) nor a level whose flag DS:0x57AA[level]
 * is already set, the player is bounced back (x = 4 or 0x130). Otherwise
 * the warp-zone entry sequence runs: blank the playfield, draw a two-column
 * tube (tile DS:0x017E[level]) with two sprites, let Dave fall from y 0 to
 * 180 with sound 2, blank again, show the extra sprite when DS:0x4F88 == 1,
 * restore the level grid from DS:0x615C, mark DS:0x57AA[level] = 1,
 * remember the level in DS:0x6152 (g_curr_warp_zone_mapping), then load
 * level DS:0x016A[level] - 1 (F_4E69) and place Dave at view column
 * DS:0x0192[level], x DS:0x01A6[level], y offset 16; shift the 4 sprite
 * slots by the new view, redraw, wait for input (F_3435) and set
 * g_is_warp_zone. The warp-target table at DS:0x016A holds 0 for levels
 * without a warp (1-based levels 5/8/9/10 have one), so a stray warp from
 * any other level loads level -1 -- the known level-6 warp bug, preserved.
 *
 * @name check_warp_transition
 * Evidence: docs/external-re-evidence.md EXT_WARP_TRANSITION_FUNCTION
 * (g_curr_warp_zone_mapping = DS:0x6152, tables +0x192/+0x1A6/+0x16A,
 * g_current_level -= 1, g_start_y = 0x10).
 */
/* @flags -G */

extern int D_56EA;              /* player x */
extern int D_56EC;              /* player y offset (g_start_y) */
extern int D_57A0;              /* first visible level column */
extern int D_573C;              /* g_is_warp_zone */
extern int D_56F4;              /* g_current_level */
extern int D_57AA[];            /* per-level "warp used" flags */
extern int D_4F86;              /* graphics-mode table index */
extern int D_0336[];
extern int D_033C[];
extern int D_573E;
extern int D_57E4;
extern int D_017E[];            /* per-level warp tube tile */
extern int D_01BA[];
extern int D_01C0[];
extern int D_4F88;
extern int D_0208;
extern int D_0214[];
extern char D_615C[];           /* saved 100x10 tile grid */
extern char *D_57A8;            /* current level tile grid */
extern int D_6152;              /* g_curr_warp_zone_mapping */
extern int D_016A[];            /* warp target level (1-based, 0 = none) */
extern int D_0192[];            /* warp target view column */
extern int D_01A6[];            /* warp target player x */
extern int D_5742[];
extern int D_574A[];
extern int D_6156;

void F_1C28(void);
void F_1C6A(void);
void F_7831(void);
void F_92D6(int x, int y, int tile);
void F_1BD6(int x, int y, int sprite);
void F_763E(int snd);
void movmem(void *src, void *dest, unsigned length);
void F_4E69(void);
void F_8EDA(void);
void F_4D9C(void);
void F_3435(void);

void F_34CB(void)
{
    int col;
    int k;
    int x, y;

    if ((D_56EC < 16 && D_57A0 == 0 && D_56EA < 2) ||
        (D_57A0 == 80 && D_56EA > 0x132)) {
        if (D_573C == 1 || D_57AA[D_56F4] == 1) {
            if (D_56EA < 2)
                D_56EA = 4;
            else
                D_56EA = 0x130;
            return;
        }
        F_1C28();
        D_573E = D_0336[D_4F86];
        D_57E4 = D_033C[D_4F86];
        F_7831();
        for (y = 0; y < 10; y++)
            for (x = 0; x < 20; x++)
                F_92D6(x, y, 0);
        F_7831();
        for (y = 0; y < 10; y++) {
            F_92D6(8, y, D_017E[D_56F4]);
            F_92D6(10, y, D_017E[D_56F4]);
        }
        F_1BD6(0x20, 0x5a, D_01BA[D_4F86]);
        F_1BD6(0xc8, 0x5a, D_01C0[D_4F86]);
        D_56EC = 0;
        D_56EA = 0x90;
        F_1C6A();
        for (k = 0; k < 30; k++)
            F_7831();
        F_763E(2);
        while (D_56EC < 180) {
            F_7831();
            F_1C28();
            F_1C6A();
            D_56EC++;
        }
        for (k = 0; k < 30; k++)
            F_7831();
        F_7831();
        for (y = 0; y < 10; y++)
            for (x = 0; x < 20; x++)
                F_92D6(x, y, 0);
        if (D_4F88 == 1)
            F_1BD6(0x48, 0xb8, D_0214[D_4F86 * D_0208]);
        movmem(D_615C, D_57A8, 1000);
        D_57AA[D_56F4] = 1;
        D_6152 = D_56F4;
        col = D_0192[D_56F4];
        x = D_01A6[D_56F4];
        D_56F4 = D_016A[D_56F4] - 1;
        F_4E69();
        D_57A0 = col;
        D_56EA = x;
        D_56EC = 16;
        for (k = 0; k < 4; k++)
            if (D_5742[k] == 1)
                D_574A[k] -= D_57A0 * 16;
        F_7831();
        F_8EDA();
        F_4D9C();
        D_6156 = (D_6156 & 0xe0) | 8;
        F_3435();
        D_573C = 1;
    }
}
