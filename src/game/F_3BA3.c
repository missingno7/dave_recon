/*
 * F_3BA3 -- level_complete()
 * cs [0x39a3,0x3dd5) / file [0x3ba3,0x3fd5), 1074 bytes.
 * Strict match: tools/match_function.py (with the 105-byte message
 * initialiser verified in _DATA at DS:0x081A).
 *
 * Runs when the level-done flag DS:0x6158 is set. Erases the trophy
 * indicator, restores the level grid, blanks the playfield and draws the
 * "between levels" corridor (rows 3 and 5 of tile 5, the door tile 2 at
 * 0,4); prints "good work! only N more to go!" (N = 9 - level patched into
 * the copied message), "this is the last level!!!" or "yes! you finished
 * the game!" -- unless returning from a warp zone -- and walks Dave across
 * the corridor (sound 10, step sound 4). Then F_769B, the level counter
 * DS:0x56F4 advances (F_0DFB is called before and after the warp-zone
 * return fix-up: a warp zone resumes at DS:0x6152), and either the next
 * level starts (F_4E69, redraw, F_3435) or, after level 10, the ending
 * plays: a tile border, the "congratulations" text (10 strings at
 * DS:0x0DB5..), and a light chasing around the 55-position border path
 * until Space is pressed; then the game-over flag DS:0x5792 is set.
 *
 * The border path tables have an off-by-one overlap: the left column
 * (positions i + 46, i = 1..8) overwrites the last bottom-row entry 47.
 * Preserved as in the original.
 *
 * @name level_complete
 * Evidence: docs/external-re-evidence.md EXT_LEVEL_COMPLETE_FUNCTION
 * (the F_769B, F_0DFB x2, F_4E69, F_7831, F_8EDA, F_4D9C, F_3435
 * sequence).
 */

/* @seg _DATA 0x081a */

struct input {
    int dir;
    int fire;
    int jet;
};

extern int D_6158;              /* level done */
extern int D_4F86;
extern int D_0208;
extern int D_0214[];
extern char D_615C[];
extern char *D_57A8;
extern int D_1392;
extern int D_8A12;              /* text cursor column */
extern int D_8A14;              /* text cursor row */
extern int D_8A22;
extern int D_56F4;              /* g_current_level */
extern int D_573C;              /* g_is_warp_zone */
extern int D_6152;              /* warp return level */
extern int D_56EA;
extern int D_56EC;
extern int D_6150;
extern int D_573E;
extern int D_57E4;
extern int D_0466[];
extern int D_047E[];
extern int D_8B32;              /* video mode */
extern int D_5792;              /* game over */
extern char D_0DB5[], D_0DD3[], D_0DF8[], D_0E19[], D_0E38[];
extern char D_0E5D[], D_0E81[], D_0EA4[], D_0EC8[], D_0EEB[];

void F_1BD6(int x, int y, int sprite);
void movmem(void *src, void *dest, unsigned length);
void F_7831(void);
void F_92D6(int x, int y, int tile);
void F_7071(char *s);
void F_1C28(void);
void F_1C6A(void);
void F_763E(int snd);
void F_769B(void);
void F_0DFB(void);
void F_4E69(void);
void F_8EDA(void);
void F_4D9C(void);
void F_3435(void);
void F_6D64(int mode);
int bioskey(int cmd);
struct input F_688C(int mode);

void F_3BA3(void)
{
    struct input in;
    int y;
    int frame;
    int pos;
    int msg_no;
    char key;
    int xs[58];
    int ys[58];
    char msg[3][35] = {
        "good work! only 9 more to go!",
        "  this is the last level!!!",
        " yes! you finished the game!"
    };
    int i, x;

    if (D_6158 == 1) {
        F_1BD6(0x48, 0xb8, D_0214[D_4F86 * D_0208]);
        movmem(D_615C, D_57A8, 1000);
        F_7831();
        for (y = 0; y < 10; y++)
            for (x = 0; x < 20; x++)
                F_92D6(x, y, 0);
        F_92D6(0, 4, 2);
        for (x = 0; x < 20; x++) {
            F_92D6(x, 3, 5);
            F_92D6(x, 5, 5);
        }
        D_1392 = -1;
        D_8A12 = 6;
        D_8A14 = 7;
        if (D_56F4 < 8) {
            msg_no = 0;
            msg[0][16] = 9 - D_56F4 + '0';
        }
        if (D_56F4 == 8)
            msg_no = 1;
        if (D_56F4 == 9)
            msg_no = 2;
        if (D_573C == 0)
            F_7071(msg[msg_no]);
        D_1392 = 0;
        D_56EA = 0x10;
        D_56EC = 0x50;
        D_573E = D_0466[D_4F86 * 4 + D_6150];
        D_57E4 = D_047E[D_4F86 * 4 + D_6150];
        F_1C6A();
        F_763E(10);
        for (D_56EA = 0x10; D_56EA < 0x130; D_56EA += 2) {
            F_7831();
            F_7831();
            F_7831();
            F_1C28();
            if (D_56EA % 3 == 2) {
                D_6150++;
                if (D_6150 > 3)
                    D_6150 = 0;
            }
            D_573E = D_0466[D_4F86 * 4 + D_6150];
            D_57E4 = D_047E[D_4F86 * 4 + D_6150];
            F_1C6A();
            if (D_56EA % 5 == 4)
                F_763E(4);
        }
        F_769B();
        D_56F4++;
        F_0DFB();
        if (D_573C == 1) {
            D_573C = 0;
            D_56F4 = D_6152;
        }
        if (D_56F4 < 10) {
            F_0DFB();
            F_4E69();
            F_7831();
            F_8EDA();
            F_4D9C();
            F_3435();
        } else {
            F_6D64(D_8B32);
            for (i = 0; i < 20; i++) {
                F_92D6(i, 0, 10);
                F_92D6(i, 9, 10);
                if (i >= 1 && i < 9) {
                    F_92D6(0, i, 10);
                    F_92D6(19, i, 10);
                }
            }
            for (i = 0; i < 20; i++) {
                xs[i] = i;
                ys[i] = 0;
            }
            for (i = 1; i < 9; i++) {
                xs[i + 19] = 19;
                ys[i + 19] = i;
            }
            for (i = 0; i < 20; i++) {
                xs[i + 28] = 19 - i;
                ys[i + 28] = 9;
            }
            for (i = 1; i < 9; i++) {
                xs[i + 46] = 0;
                ys[i + 46] = 9 - i;
            }
            D_1392 = -1;
            D_8A22 = 3;
            D_8A12 = D_8A22;
            D_8A14 = 5;
            F_7071(D_0DB5);
            F_7071(D_0DD3);
            F_7071(D_0DF8);
            F_7071(D_0E19);
            F_7071(D_0E38);
            F_7071(D_0E5D);
            F_7071(D_0E81);
            F_7071(D_0EA4);
            F_7071(D_0EC8);
            F_7071(D_0EEB);
            D_1392 = 0;
            frame = 0;
            pos = 0;
            do {
                if (frame % 4 == 0)
                    F_7831();
                key = bioskey(1);
                if (++frame > 3)
                    frame = 0;
                F_92D6(xs[pos], ys[pos], frame + 10);
                if (++pos > 54)
                    pos = 0;
                in = F_688C(1);
            } while (key != ' ');
            bioskey(0);
            D_5792 = 1;
        }
    }
}
