/*
 * F_15A5 -- handle_death
 * cs [0x13a5,0x1580) / file [0x15a5,0x1780), 475 bytes.
 *
 * Runs while Dave is dying (D_6156 bit 0x20 clear) once the death timer
 * D_6546 expires: removes a life icon, and either ends the game (lives < 0:
 * clears trophy/jetpack icons, D_5792 = game over, restores the level
 * tiles) or restarts the level: re-applies the scroll offset to the doors,
 * resets Dave's start position/state from the per-level tables (or the warp
 * zone tables when D_573C), clears all monsters (6 x 0x13A) and shots
 * (5 x 0xE) and redraws.
 * @name handle_death -- evidence: g_lives decrement, game-over flag.
 *
 * Codegen: built with -G (2-byte argument cleanup is inc sp; inc sp).
 * `if (--x == -1)` compiles to dec [x]; mov ax,[x]; cmp ax,-1.
 */

#include <mem.h>
struct obj {
    int active;
    char rest[0x13a - 2];
};
struct shot {
    int active;
    char rest[0xe - 2];
};
extern int D_6156;
extern int D_6546;
extern int D_56EE;
extern int D_4F86;
extern int D_0208;
extern int D_020A[];
extern int D_4F8A;
extern int D_4F84;
extern int D_5792;
extern char *D_57A8;
extern char D_615C[];
extern int D_5742[];
extern int D_574A[];
extern int D_57A0;
extern int D_56F4;
extern unsigned char D_0118[];
extern int D_0122[];
extern int D_0136[];
extern int D_56EA;
extern int D_56EC;
extern int D_5794;
extern int D_6548;
extern int D_0336[];
extern int D_033C[];
extern int D_573E;
extern int D_57E4;
extern int D_6150;
extern int D_57E2;
extern int D_5740;
extern int D_573C;
extern int D_6152;
extern int D_0192[];
extern int D_01A6[];
extern struct obj D_4F8E[];
extern struct shot D_56F6[];
void F_1BD6(int, int, int);
void F_371F(void);
void F_1C6A(void);
void F_7831(void);
void F_8EDA(void);
void F_4D9C(void);
void F_3435(void);

void F_15A5(void)
{
    int i;

    if (D_6156 & 0x20)
        return;
    if (--D_6546)
        return;
    if (D_56EE > 0)
        F_1BD6((D_56EE - 1) * 16 + 0x100, 0, D_020A[D_4F86 * D_0208 + 6]);
    if (--D_56EE == -1) {
        if (D_4F8A == 1) {
            F_1BD6(0, 0xaa, D_020A[D_0208 * D_4F86]);
            F_371F();
        }
        if (D_4F84 == 1)
            F_1BD6(0xf0, 0xaa, D_020A[D_0208 * D_4F86 + 1]);
        D_5792 = 1;
        movmem(D_615C, D_57A8, 1000);
        return;
    }
    for (i = 0; i < 4; i++)
        if (D_5742[i] == 1)
            D_574A[i] += D_57A0 * 16;
    D_57A0 = 0;
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
    if (D_573C == 1) {
        D_57A0 = D_0192[D_6152];
        D_56EA = D_01A6[D_6152];
        D_56EC = 0x10;
        D_6156 = 0x28;
        for (i = 0; i < 4; i++)
            if (D_5742[i])
                D_574A[i] -= D_57A0 * 16;
    }
    F_1C6A();
    for (i = 0; i < 6; i++)
        D_4F8E[i].active = 0;
    for (i = 0; i < 5; i++)
        D_56F6[i].active = 0;
    F_7831();
    F_8EDA();
    F_4D9C();
    F_3435();
}
