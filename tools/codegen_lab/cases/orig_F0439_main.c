/*
 * @behaviour: REAL FUNCTION _main (file 0x439..0x4d2, 153 bytes) reproduced
 *   byte-for-byte modulo fixups. Shows: (1) a 3-case switch is a compare
 *   chain, values compared in ascending order (3,4,5) while the case bodies
 *   stay in source order; (2) the last case's `break` still emits
 *   `jmp $+2` (eb 00) -- no -O; (3) `x = f(); switch (x)` stores then
 *   reloads the global (a3 c0 9e / a1 c0 9e); (4) a 2-byte argument is
 *   cleaned up with `inc sp; inc sp` (44 44) -- that is -G.
 * @original: 0x439 0x4d2
 * @contrast: -O        # jump optimisation deletes the eb 00 jumps
 *   -G-                # cleanup becomes pop cx (59)
 *   -O -Z
 *   -p                 # pascal calling convention
 * @same-as: -Z         # -Z alone changes nothing (needs -O to act)
 *   -k
 *   -a
 *   -d
 *   -K
 *   -r-
 */
extern int g_9ec0, g_8b32, g_aa, g_5792, g_579c;
void f_4f9b(void); int f_7a59(void); void f_1121(void); void f_7de(void);
void f_4827(void); void f_1b16(void); void f_16f6(void); void f_2b87(void);
void f_2e1b(void); void f_312c(void); void f_35ed(void); void f_3dd5(void);
void f_39a3(void); void f_32cb(void); void f_1580(void); void f_13a5(void);
void f_2fc(void); void f_2d2(int);

void main(void)
{
    f_4f9b();
    g_9ec0 = f_7a59();
    switch (g_9ec0) {
    case 4:
    case 5:
        g_8b32 = 3;
        break;
    case 3:
        g_8b32 = 2;
        break;
    default:
        g_8b32 = 1;
        break;
    }
    f_1121();
    do {
        g_aa = 3;
        do {
            f_7de(); f_4827(); f_1b16(); f_16f6(); f_2b87(); f_2e1b(); f_312c();
            f_35ed(); f_3dd5(); f_39a3(); f_32cb(); f_1580(); f_13a5();
        } while (g_5792 == 0);
        g_5792 = 0;
        if (g_579c == 0)
            f_2fc();
    } while (g_579c == 0);
    f_2d2(0);
}
