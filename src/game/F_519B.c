/*
 * F_519B -- init_game_once()
 * cs [0x4f9b,0x515a) / file [0x519b,0x535a), 447 bytes.
 * EXACT (strict): 43 fixups incl. the far segments 1C2E/0B31 (MZ relocations
 * verified) and the SCOPY'd initialiser in _DATA at DS:0x0883.
 *
 * One-time start-up: allocates the 0x16000-byte far work buffer
 * (F_6A62, result to DS:0x56F0), calls the asm stub F_8516 (sets the far
 * level pointer DS:0x13AC), points g_sound_data (DS:0x137A) at the far
 * PC-speaker sound segment 1C2E:0000, runs F_75D6 and F_6293, points
 * g_demo_data (DS:0x57A4) at the far demo-recording segment 0B31:0000,
 * mallocs the 45-byte high-score file buffer (DS:0x4F8C) and loads
 * "DSCORES.DAV" (DS:0x00AE) into it via F_6ADE; if that fails, writes the
 * default table (initialised local copied from DS:0x0883: five entries
 * of level 1, score "00100", initials "JON") with F_6B94 and uses it.
 * Then F_535A (init_game_state), clears DS:0x579C and decodes the five
 * 9-byte file entries (level byte, five score digit bytes, three initials)
 * into the 7-byte high-score records at DS:0x57BE.
 *
 * @name init_game_once
 * Evidence: docs/data-layout.md (g_sound_data = 1C2E:0000, g_demo_data
 * = 0B31:0000 set here; DSCORES.DAV string at DS:0x00AE).
 *
 * Codegen note: the far pointer to `def` is pushed as `lea ax; push ds;
 * push ax`. A plain near->far conversion gives `push ss`/`push ds` first;
 * converting through `long` (`(char far *)(long)def`) reproduces the
 * original order (the same idiom matches F_6DC2's near->far conversions).
 */
/* @seg _DATA 0x0883 */

#include <dos.h>
#include <mem.h>

struct hsfile {
    char level;
    char digit[5];
    char name[3];
};

struct hiscore {
    int level;
    int score;
    char name[3];
};

extern void far *D_56F0;        /* far work buffer */
extern char far *D_137A;        /* g_sound_data */
extern char far *D_57A4;        /* g_demo_data */
extern char far P1C2E_0000[];       /* far segment 1C2E: PC-speaker sounds */
extern char far P0B31_0000[];       /* far segment 0B31: demo recordings */
extern struct hsfile *D_4F8C;   /* high-score file buffer */
extern char D_00AE[];           /* "DSCORES.DAV" */
extern int D_579C;
extern struct hiscore D_57BE[];

void far *F_6A62(unsigned long size);
void F_8516(void);
void F_75D6(void);
void F_6293(void);
void *malloc(unsigned size);
long F_6ADE(char *name, void far *buf);
void F_6B94(char *name, void far *buf, long len);
void F_535A(void);

void F_519B(void)
{
    struct hsfile def[5] = {
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } },
        { 1, { 0, 0, 1, 0, 0 }, { 'J', 'O', 'N' } }
    };
    int i;

    D_56F0 = F_6A62(0x16000L);
    F_8516();
    D_137A = P1C2E_0000;
    F_75D6();
    F_6293();
    D_57A4 = P0B31_0000;
    D_4F8C = malloc(45);
    if (F_6ADE(D_00AE, D_4F8C) == 0) {
        F_6B94(D_00AE, (char far *)(long)def, 45L);
        movedata(_DS, (unsigned)def, _DS, (unsigned)D_4F8C, 45);
    }
    F_535A();
    D_579C = 0;
    for (i = 0; i < 5; i++) {
        D_57BE[i].score = D_4F8C[i].digit[0] * 10000 + D_4F8C[i].digit[1] * 1000 +
                          D_4F8C[i].digit[2] * 100 + D_4F8C[i].digit[3] * 10 +
                          D_4F8C[i].digit[4];
        D_57BE[i].level = D_4F8C[i].level;
        D_57BE[i].name[0] = D_4F8C[i].name[0];
        D_57BE[i].name[1] = D_4F8C[i].name[1];
        D_57BE[i].name[2] = D_4F8C[i].name[2];
    }
}
