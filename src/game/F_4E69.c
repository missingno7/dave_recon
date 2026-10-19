/*
 * F_4E69 -- load_level()
 * cs [0x4c69,0x4f9b) / file [0x4e69,0x519b), 818 bytes.
 * Strict match: tools/match_function.py.
 *
 * Sets up level DS:0x56F4 (g_current_level, 0-based): reseeds rand with
 * 100, loads the per-level option bits (byte table DS:0x0118) into
 * DS:0x6156 and Dave's start x/y (DS:0x0122/0x0136) into DS:0x56EA/EC,
 * resets the player animation state, and points DS:0x57A8 at the level
 * record g_levels[level] (near pointer at DS:0x13AC, 0x500-byte records:
 * 256-byte monster path then 100x10 tiles). Clears the actor (6), object
 * (5) and animated-tile (200) tables, then scans the 1000 tiles: every
 * tile equal to one of the 4 animated base tiles DS:0x034E[k] gets an
 * animated-tile record (base, random start frame within the
 * DS:0x0356[k]-frame cycle, column, row, frame count; the next record's
 * count is zeroed as terminator). Copies the level's 80-byte monster
 * block DS:0x0496[level] into the monster arrays at DS:0x5742, gives each
 * monster a random start frame and its per-mode sprite base, sets the
 * monster path pointer DS:0x614C (huge) to the record start, advances
 * DS:0x57A8 to the tile map and copies it to the working grid DS:0x615C,
 * resets the view column and redraws the status items flagged in
 * DS:0x4F84 / DS:0x4F8A.
 *
 * @name load_level
 * Evidence: data lane (g_levels at DGROUP:0x173A, 10 x 0x500, pointer at
 * DS:0x13AC; F_4E69 = loader); level index -1 (level-6 warp bug) reads
 * the record before g_levels.
 *
 * Codegen notes: `(long)rand() * n / 32767` compiles to push 0:7FFF,
 * rand, cwd, N_LXMUL@, N_LDIV@. The terminator store
 * `t[n + 1].count = 0` folds into `[bx + 0x57FE]` with bx = n * 12.
 * Here every switch case ends with `break`.
 */


struct anim {
    int active;
    int first;
    int cur;
    int col;
    int row;
    int count;
};

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

struct monsters {
    int w[40];
};

extern int D_6158;
extern unsigned char D_0118[];  /* per-level option bits */
extern int D_6156;
extern int D_56F4;              /* g_current_level */
extern int D_0122[];            /* level start x */
extern int D_0136[];            /* level start y */
extern int D_56EA;
extern int D_56EC;
extern int D_5794;
extern int D_6548;
extern int D_4F86;
extern int D_0336[];
extern int D_033C[];
extern int D_573E;
extern int D_57E4;
extern int D_6150;
extern int D_57E2;
extern int D_5740;
extern char *D_57A8;            /* current level record / tile map */
extern char *D_13AC;            /* g_levels */
extern int D_5796;
extern struct actor D_4F8E[];
extern struct obj D_56F6[];
extern struct anim D_57E8[];
extern int D_034E[];            /* animated base tiles */
extern int D_0356[];            /* their frame counts */
extern struct monsters D_5742;
extern struct monsters D_0496[];
extern int D_5762[];
extern int D_576A[];
extern int D_5772[];
extern int D_577A[];
extern int D_5782[];
extern int D_578A[];
extern char huge *D_614C;       /* monster path */
extern char D_615C[];           /* working tile grid */
extern int D_57A0;
extern int D_4F84;
extern int D_4F88;
extern int D_4F8A;
extern int D_0208;
extern int D_020A[];
extern int D_020C[];

void srand(unsigned seed);
int rand(void);
void movmem(void *src, void *dest, unsigned length);
void F_1BD6(int x, int y, int sprite);
void F_371F(void);

void F_4E69(void)
{
    int col;
    int row;
    int tile;
    int k;
    int i;
    int n;

    D_6158 = 0;
    srand(100);
    D_6156 = D_0118[D_56F4];
    D_56EA = D_0122[D_56F4];
    D_56EC = D_0136[D_56F4];
    D_5794 = 3;
    D_6548 = 2;
    D_573E = D_0336[D_4F86];
    D_57E4 = D_033C[D_4F86];
    D_6150 = 0;
    D_57E2 = 8;
    D_5740 = 1;
    D_57A8 = D_13AC + D_56F4 * 0x500;
    D_5796 = 3;
    for (i = 0; i < 6; i++)
        D_4F8E[i].active = 0;
    for (i = 0; i < 5; i++)
        D_56F6[i].active = 0;
    for (i = 0; i < 200; i++)
        D_57E8[i].active = 0;
    n = 0;
    col = 0;
    row = 0;
    for (i = 0; i < 1000; i++) {
        tile = D_57A8[i + 0x100];
        for (k = 0; k < 4; k++) {
            if (D_034E[k] == tile) {
                D_57E8[n].active = 1;
                D_57E8[n].first = tile;
                D_57E8[n].cur = tile + (long)rand() * D_0356[k] / 32767;
                D_57E8[n].col = col;
                D_57E8[n].row = row;
                D_57E8[n].count = D_0356[k];
                D_57E8[n + 1].count = 0;
                n++;
            }
        }
        col++;
        if (col == 100) {
            col = 0;
            row++;
        }
    }
    D_5742 = D_0496[D_56F4];
    for (i = 0; i < 4; i++) {
        D_5772[i] = 2;
        D_577A[i] = (long)rand() * 3 / 32767;
        D_578A[i] = 5;
        D_5782[i] = D_5762[i];
        switch (D_4F86) {
        case 0:
            D_576A[i] = (D_56F4 - 2) * 8 + 0x7d;
            break;
        case 1:
            D_576A[i] = (D_56F4 - 2) * 8 * 2 + 0xc5;
            break;
        case 2:
            D_576A[i] = (D_56F4 - 2) * 4 + 0x59;
            break;
        }
    }
    D_614C = D_57A8;
    D_57A8 += 0x100;
    movmem(D_57A8, D_615C, 1000);
    D_57A0 = 0;
    if (D_4F84 == 1)
        F_1BD6(0xf0, 0xaa, D_020C[D_4F86 * D_0208]);
    if (D_4F8A == 1) {
        F_371F();
        F_1BD6(0, 0xaa, D_020A[D_4F86 * D_0208]);
    }
    D_4F8A = 0;
    D_4F88 = 0;
    D_4F84 = 0;
}
