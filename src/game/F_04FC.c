/*
 * F_04FC .. F_0C34 -- six consecutive functions of the main game module,
 * compiled together because they share the module's initialised _DATA run
 * DS [0x07B6,0x07D4): the SCOPY initialisers of their local char buffers.
 *
 *   F_04FC  cs [0x02fc,0x05eb)  check_high_score     751 bytes
 *   F_07EB  cs [0x05eb,0x068e)  input_initials       163 bytes
 *   F_088E  cs [0x068e,0x07de)  show_high_scores     336 bytes
 *   F_09DE  cs [0x07de,0x09b2)  attract_mode         468 bytes
 *   F_0BB2  cs [0x09b2,0x0a34)  draw_status_bar      130 bytes
 *   F_0C34  cs [0x0a34,0x0bfb)  update_score         455 bytes
 *
 * Why one file: all of these buffers except F_0C34's "00000" are zero, and
 * TCC emits no LEDATA for an all-zero _DATA, so a single-function file for
 * F_04FC or F_088E has a SEGDEF-only _DATA that tools/match_function.py
 * cannot compare (it calls segment_bytes("_DATA") and raises). Compiled as
 * one unit, the _DATA is 30 bytes ending in "00000\0" and is compared in
 * full against DS 0x07B6.
 *
 * The module's string literals are pooled after all its initialised data
 * (DS 0x08B0...), so they are referenced by address (D_08B0 ...) rather than
 * written as literals; their text is quoted at each extern.
 *
 * Codegen notes (TCC 1.00, -G needed: 2-byte arg cleanup is inc sp/inc sp):
 * - block-scoped locals are placed below every function-level local AND
 *   below the struct-return temporaries of the whole function (F_04FC: len,
 *   num, digits come after s and the F_688C temp); within a block the first
 *   declared gets the highest address.
 * - the first two int locals declared are the SI and DI register variables.
 * - `c = toupper(key = F_7005())` gives `mov di,ax; push ax` (F_07EB).
 * - a struct-returning call `s = F_688C(1)` pushes &s, the args, a far
 *   pointer to a temporary, then SCOPYs temp -> s.
 * - D_01F0 is indexed as a flat array: `D_01F0[D_4F86 * 4 + (i & 3)]`
 *   (shl,shl,add,shl); a 2-D array gives shl,shl,shl / shl.
 * - the last case of F_09DE's switch has no break (no trailing jmp).
 */
/* @flags -G */
/* @seg _DATA 0x07b6 */
#include <bios.h>
#include <ctype.h>
#include <mem.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

struct joy {                    /* returned by F_688C (input poll) */
    int a;
    int b;                      /* non-zero: button pressed */
    int c;
};
struct hiscore {                /* 9-byte DSCORES.DAV record */
    char level;
    char score[5];              /* decimal digits 0..9 */
    char name[3];
};
struct entry {                  /* 7-byte in-memory high score entry */
    int level;
    unsigned score;
    char name[3];
};

extern struct entry D_57BE[];   /* in-memory high score entries */
extern struct hiscore *D_4F8C;  /* DSCORES.DAV image (5 records) */
extern unsigned long D_4C60;    /* g_score */
extern unsigned long D_6148;    /* next extra-life score */
extern int D_56EE;              /* g_lives */
extern int D_56F4;              /* g_current_level */
extern int D_00AA;              /* game state: 0 play, 1 demo, 2 scores, 3 title */
extern int D_4F86;              /* gfx index (video mode - 1) */
extern int D_0208;              /* tiles per gfx mode in D_020A */
extern int D_020A[];            /* status-bar tile ids, D_0208 per mode */
extern int D_01EA[];            /* digit-0 tile id per mode */
extern int D_01F0[];            /* title animation tile ids, 4 per mode */
extern int D_4F84;              /* has jetpack */
extern int D_4F88;              /* has gun */
extern int D_4F8A;              /* has trophy */
extern int D_8A12;              /* text cursor column */
extern int D_8A14;              /* text cursor row */
extern int D_8A22;
extern char far *D_57A4;        /* demo data */
extern int D_57A2;              /* demo read position */
extern char D_00AE[];           /* "DSCORES.DAV" */
extern char D_08B0[];           /* "You got a high score!" */
extern char D_08C6[];           /* "Game Over" */
extern char D_08D0[];           /* "High Scores\r\n\nScore  Name  Level\r\n-----  ----  -----\r\n" */
extern char D_0907[];           /* "\n\n\r" */

void F_088E(int);
void F_07EB(char *);
void F_6DC2(int, int, int, int);
void F_7071(char *);
void F_6B94(char *, void far *, long);
void F_7831(void);
struct joy F_688C(int);
void F_2D87(void);
void F_301B(void);
void F_332C(void);
void F_18F6(void);
int F_7005(void);
void F_7878(int, int, int);
void F_770A(void);
void F_763E(int);
void F_6EF1(int, int);
void F_4997(void);
void F_535A(void);
void F_4E69(void);
void F_13FF(void);
void F_3435(void);
void F_1B84(int, int, int);
void F_1BD6(int, int, int);
void F_92D6(int, int, int);
void F_371F(void);
void F_0C34(void);
void F_0DFB(void);

/*
 * F_04FC check_high_score: called by main when the game ends. If the score
 * beats an entry, shifts the table down, inserts score/level, converts the
 * score to 5 digits, shows the table, asks for initials (F_07EB) and writes
 * DSCORES.DAV (F_6B94). Otherwise shows "Game Over" (levels 1-10) while the
 * monsters keep animating until a key/button or ~1000 frames.
 * Name evidence: strings "You got a high score!", "Game Over", "DSCORES.DAV".
 * Quirk preserved: the in-memory entry keeps only the low word of the score.
 */
void F_04FC(void)
{
    struct joy s;
    int j;
    int i;

    for (i = 0; i < 5; i++) {
        if (D_57BE[i].score < D_4C60) {
            int len;
            char num[6] = "";
            char digits[6] = "";

            for (j = 4; j > i; j--) {
                D_57BE[j].score = D_57BE[j - 1].score;
                D_57BE[j].level = D_57BE[j - 1].level;
                movmem(D_57BE[j - 1].name, D_57BE[j].name, 3);
                movmem(&D_4F8C[j - 1], &D_4F8C[j], 9);
            }
            D_57BE[i].score = D_4C60;
            D_57BE[i].level = D_56F4 + 1;
            setmem(D_57BE[i].name, 3, 0);
            setmem(D_4F8C[i].name, 3, 0);
            D_4F8C[i].level = D_56F4 + 1;
            ultoa(D_4C60, num, 10);
            len = strlen(num);
            for (j = 0; j < len; j++)
                digits[4 - j] = num[len - 1 - j] - '0';
            movmem(digits, D_4F8C[i].score, 5);
            F_088E(1);
            F_6DC2(0, 0x16, 0x27, 0x18);
            D_8A12 = 10;
            D_8A14 = 0x17;
            F_7071(D_08B0);
            D_8A12 = 0x13;
            D_8A14 = i * 2 + 10;
            F_07EB(D_57BE[i].name);
            movmem(D_57BE[i].name, D_4F8C[i].name, 3);
            F_6B94(D_00AE, (void far *)D_4F8C, 0x2dL);
            return;
        }
    }
    if (D_56F4 < 10) {
        F_6DC2(0, 0x16, 0x27, 0x18);
        D_8A12 = 0xf;
        D_8A14 = 0x17;
        F_7071(D_08C6);
        if (bioskey(1))
            bioskey(0);
        for (i = 0; i < 1000; i++) {
            F_7831();
            s = F_688C(1);
            F_2D87();
            F_301B();
            F_332C();
            F_18F6();
            if (bioskey(1) || s.b)
                break;
        }
    }
}

/*
 * F_07EB input_initials(name): flushes one pending key, then reads keys,
 * accepting up to 3 characters ' '..'Z' (upper-cased) echoed at the text
 * cursor via F_7878; Left-arrow (scan 0x4B) or Backspace (scan 0x0E) erases
 * one; Enter ends. Name evidence: called with the 3-byte name field of a
 * high score entry right after "You got a high score!".
 */
void F_07EB(char *name)
{
    int n;
    int key;
    char c;

    n = 0;
    if (bioskey(1))
        bioskey(0);
    do {
        c = toupper(key = F_7005());
        if (c >= ' ' && c <= 'Z' && n < 3) {
            name[n++] = c;
            F_7878(D_8A12++, D_8A14, c);
        }
        if (((key >> 8) == 0x4b || (key >> 8) == 0x0e) && n > 0) {
            F_7878(--D_8A12, D_8A14, ' ');
            n--;
        }
    } while (c != '\r');
}

/*
 * F_088E show_high_scores(with_sound): draws the "High Scores" table from
 * the DSCORES.DAV records: 5 score digits, 3 initials, and the level
 * (10 -> "10", 11 -> "won"). With a non-zero argument it plays sounds
 * (F_763E 0xB / 6) and waits (F_770A) between rows.
 */
void F_088E(int flag)
{
    int k;
    int i;

    F_770A();
    if (flag)
        F_763E(0xb);
    for (i = 4; i < 0x1a; i += 2)
        F_6EF1(i, i / 2);
    D_8A12 = 0x10;
    D_8A14 = 6;
    D_8A22 = 0xc;
    F_7071(D_08D0);
    for (i = 0; i < 5; i++) {
        char buf[6] = "";
        char lvl;

        if (flag)
            F_763E(6);
        for (k = 0; k < 5; k++)
            buf[k] = D_4F8C[i].score[k] + '0';
        F_7071(buf);
        for (k = 0; k < 3; k++)
            buf[k] = D_4F8C[i].name[k];
        buf[3] = 0;
        D_8A12 = 0x13;
        F_7071(buf);
        lvl = D_4F8C[i].level;
        buf[0] = lvl + '0';
        buf[1] = 0;
        D_8A12 = 0x1b;
        if (lvl == 10) {
            buf[0] = '1';
            buf[1] = '0';
            buf[2] = 0;
        }
        if (lvl == 11) {
            buf[0] = 'w';
            buf[1] = 'o';
            buf[2] = 'n';
            buf[3] = 0;
            D_8A12--;
        }
        F_7071(buf);
        F_7071(D_0907);
        if (flag)
            F_770A();
    }
}

/*
 * F_09DE attract_mode: first thing in main's game loop. State 2 shows the
 * high score table for ~1000 frames, state 3 the animated title for 200
 * frames; a key or button starts a game (state 0), otherwise a random demo
 * (srand(time), rand()) is selected from D_57A4 and state 1 (demo) begins.
 * Quirk preserved: the title animation counter j is never initialised.
 */
void F_09DE(void)
{
    int flag;
    struct joy s;
    int i;
    int j;

    switch (D_00AA) {
    case 2:
        F_088E(1);
        for (i = 0; i < 1000; i++) {
            F_7831();
            F_4997();
            s = F_688C(1);
            if (flag = bioskey(1) || s.b)
                break;
        }
        if (flag) {
            D_00AA = 0;
            F_535A();
            F_4E69();
            F_13FF();
            F_3435();
            break;
        }
        D_00AA++;
    case 3:
        F_13FF();
        for (i = 0; i < 200; i++) {
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_7831();
            F_4997();
            F_1B84(0x68, 0, D_01F0[D_4F86 * 4 + (i & 3)]);
            j++;
            F_92D6(8, 7, (j & 3) + 6);
            F_92D6(0xd, 9, (j & 3) + 6);
            s = F_688C(1);
            if (flag = bioskey(1) || s.b)
                break;
        }
        F_535A();
        if (flag) {
            D_00AA = 0;
            F_4E69();
            F_13FF();
            F_3435();
            break;
        }
        srand(time(NULL));
        D_57A2 = *(int far *)(D_57A4 + (int)((long)rand() * *D_57A4 / 32767) * 4 + 4);
        D_00AA = 1;
        D_56F4 = D_57A4[D_57A2];
        D_57A2++;
        F_4E69();
        F_13FF();
    }
}

/*
 * F_0BB2 draw_status_bar: draws the trophy (after F_371F), jetpack and gun
 * indicators if held, then the score (F_0C34) and level number (F_0DFB).
 */
void F_0BB2(void)
{
    if (D_4F8A) {
        F_371F();
        F_1BD6(0, 0xaa, D_020A[D_4F86 * D_0208]);
    }
    if (D_4F84)
        F_1BD6(0xf0, 0xaa, D_020A[D_4F86 * D_0208 + 1]);
    if (D_4F88)
        F_1BD6(0x48, 0xb8, D_020A[D_4F86 * D_0208 + 5]);
    F_0C34();
    F_0DFB();
}

/*
 * F_0C34 update_score: every 20000 points awards an extra life (max 3 shown,
 * drawn at x = 0x100 + 16*lives) and rounds the next-goal down to a
 * multiple of 20000; caps the score at 99999; draws it as 5 zero-padded
 * digit tiles at x = 0x40..0x60. Matches the external RE's score/lives
 * description (constants 0x4E20, 0x1869F).
 */
void F_0C34(void)
{
    char num[6] = "";
    char digits[6] = "00000";

    if (D_4C60 - D_6148 >= 20000) {
        D_6148 = D_4C60;
        D_6148 = D_6148 / 20000 * 20000;
        if (D_56EE < 3) {
            F_1BD6(D_56EE * 16 + 0x100, 0, D_020A[D_0208 * D_4F86 + 6]);
            D_56EE++;
            F_763E(0xc);
        }
    }
    if (D_4C60 > 99999L)
        D_4C60 = 99999L;
    ultoa(D_4C60, num, 10);
    movmem(num, digits + (5 - strlen(num)), strlen(num));
    F_1B84(0x40, 1, D_01EA[D_4F86] + digits[0] - '0');
    F_1B84(0x48, 1, D_01EA[D_4F86] + digits[1] - '0');
    F_1B84(0x50, 1, D_01EA[D_4F86] + digits[2] - '0');
    F_1B84(0x58, 1, D_01EA[D_4F86] + digits[3] - '0');
    F_1B84(0x60, 1, D_01EA[D_4F86] + digits[4] - '0');
}
